import sys
import os
import json
import asyncio
import re
import time
from collections import defaultdict
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import httpx

# Insert backend folder to sys.path to prevent module import issues on deployment hosts
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from indexer import MNDIndexer
from guardrails import sanitize_input, validate_output

app = FastAPI(title="Australian MND Assistant API", version="2.0")

# In-memory rate limiter: max 10 requests per 60 seconds per IP
RATE_LIMIT_WINDOW = 60  # seconds
RATE_LIMIT_MAX = 10
_rate_store: dict[str, list[float]] = defaultdict(list)

def check_rate_limit(client_ip: str) -> bool:
    """Returns True if request is allowed, False if rate limited."""
    now = time.time()
    window_start = now - RATE_LIMIT_WINDOW
    # Prune old entries
    _rate_store[client_ip] = [t for t in _rate_store[client_ip] if t > window_start]
    if len(_rate_store[client_ip]) >= RATE_LIMIT_MAX:
        return False
    _rate_store[client_ip].append(now)
    return True

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_DIR = os.path.join(BASE_DIR, "static")

# Load DEEPSEEK_API_KEY from .env file if present
ENV_FILE = os.path.join(BASE_DIR, ".env")
if os.path.exists(ENV_FILE):
    with open(ENV_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line_str = line.strip()
            if line_str.startswith("DEEPSEEK_API_KEY="):
                os.environ["DEEPSEEK_API_KEY"] = line_str.split("=", 1)[1].strip().strip('"').strip("'")

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "").strip()

IMAGE_MAP = {}

def build_image_map():
    global IMAGE_MAP
    IMAGE_MAP = {}
    assets_dir = os.path.join(BASE_DIR, "images", "assets")
    if not os.path.exists(assets_dir):
        print(f"Images assets directory not found at: {assets_dir}", flush=True)
        return
    for root, dirs, files in os.walk(assets_dir):
        for file in files:
            ext = os.path.splitext(file)[1].lower()
            if ext in [".png", ".jpg", ".jpeg", ".webp", ".svg"]:
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, BASE_DIR).replace("\\", "/")
                name_part = os.path.splitext(file)[0]
                if "-" in name_part:
                    parts = name_part.rsplit("-", 1)
                    rightmost = parts[1].strip()
                    if len(rightmost) >= 8 and len(rightmost) <= 12 and re.match(r'^[a-f0-9]+$', rightmost):
                        name_part = parts[0].strip()
                from urllib.parse import quote
                norm_name = re.sub(r'[^a-z0-9]', '', name_part.lower())
                IMAGE_MAP[norm_name] = "/" + quote(rel_path, safe="/")
    print(f"Indexed {len(IMAGE_MAP)} product/care images.", flush=True)

def find_image_for_query(query: str) -> str:
    norm_query = re.sub(r'[^a-z0-9]', '', query.lower())
    if not norm_query:
        return ""
    if norm_query in IMAGE_MAP:
        return IMAGE_MAP[norm_query]
    for key, path in IMAGE_MAP.items():
        if key in norm_query or norm_query in key:
            return path
    return ""

os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

IMAGES_DIR = os.path.join(BASE_DIR, "images")
if os.path.exists(IMAGES_DIR):
    app.mount("/images", StaticFiles(directory=IMAGES_DIR), name="images")

indexer = MNDIndexer()

@app.on_event("startup")
def startup_event():
    indexer.load_index()
    build_image_map()

EMERGENCY_KEYWORDS = [
    "can't breathe", "cannot breathe", "choking", "choke",
    "severe shortness of breath", "blue lips", "chest pain",
    "suffocating", "severe dyspnea", "unresponsive"
]

def check_emergency(text: str) -> bool:
    text_lower = text.lower()
    return any(kw in text_lower for kw in EMERGENCY_KEYWORDS)

SYSTEM_PROMPT_TEMPLATE = """You are the Australian MND/ALS Assistant — a super friendly, playful, engaging, and deeply supportive AI buddy here to help people living with Motor Neurone Disease (MND/ALS), their awesome carers, families, and healthcare teams across Australia!

✨ Tone & Playful Personality Guidelines:
- **Playful, Warm & Uplifting:** Be vibrant, enthusiastic, conversational, and genuinely engaging! Use friendly Aussie warmth (e.g. "G'day!", "Hey there! Great question!", "Let's get this sorted out together!").
- **Engaging & Visual:** Use expressive emojis (✨, ♿, 🦘, 💡, 💙, 🌟, 📑), bullet points, and encouraging check-ins to make reading fun, easy, and lighthearted.
- **Accurate & Empowering:** Keep all NDIS funding, equipment loan libraries (like FlexEquip or SWEP), clinical care tips, and state guidelines 100% accurate, but explain them in an encouraging, upbeat, and accessible way!
- **Visually Rich (Images):** When recommending specific equipment or services (e.g. wheelchairs, commodes, switch mounts, feeding tubes, etc.), if the retrieved context for that item includes an 'Image URL' property, you MUST embed it directly inline in your response on its own line using standard Markdown image syntax: `![Item Name](image_url)` so the user gets a helpful visual preview of the product! Do NOT modify the image_url path or prepend any domain name (e.g., do not add 'https://flexequip.com.au' or similar). Use the exact relative path provided.

🎯 MANDATORY REGIONAL INSTRUCTION FOR USER LOCATION:
The user has specifically selected the target state/region: **{selected_state}**.
You MUST explicitly tailor your answer, equipment pathways, funding schemes, and support services specifically for **{selected_state}**:
- If {selected_state} is NSW or ACT: Give a huge shoutout to **FlexEquip** (the awesome MND NSW equipment loan service), MND NSW advisors, and EnableNSW!
- If {selected_state} is VIC: Highlight **SWEP** (Statewide Equipment Program), MND Victoria, and Victorian Health pathways!
- If {selected_state} is QLD: Highlight **MASS** (Medical Aids Subsidy Scheme) and MND Queensland!
- If {selected_state} is WA: Highlight MND Western Australia advisors and local WA Health pathways!
- If {selected_state} is SA: Highlight MND South Australia advisors and SA health pathways!
- In your opening line, greet the user warmly and state: *"G'day! Here is your custom guide tailored specifically for **{selected_state}**:"*

Relevant Retrieved Context from Australian MND Knowledge Base:
{context_block}

⚠️ CRITICAL RULE — NEVER OMIT THIS:
At the VERY END of EVERY response, you MUST ALWAYS include a section titled:
### 📚 Verified Sources & Reference Links
List every source used from the context above as a bullet point with a clickable Markdown link:
- [Source Title — Publisher Name](exact_url)
You are FORBIDDEN from generating a response without this sources section. This is a hard requirement.
"""

@app.get("/", response_class=HTMLResponse)
async def read_root():
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h2>MND Assistant Backend Running. Creating frontend...</h2>")

@app.get("/api/stats")
async def get_stats():
    return {
        "total_documents": len(indexer.documents),
        "total_entities": len(indexer.entities),
        "has_api_key": bool(DEEPSEEK_API_KEY),
        "status": "online"
    }

@app.post("/api/search")
async def search_endpoint(payload: dict):
    query = payload.get("query", "")
    state = payload.get("state", "National")
    if not query:
        raise HTTPException(status_code=400, detail="Query string is required")
        
    docs = indexer.search_documents(query, state=state, top_k=5)
    entities = indexer.search_entities(query, state=state, top_k=4)
    
    # Attach images if found
    for ent in entities:
        ent["image_url"] = find_image_for_query(ent.get("name", ""))
    for doc in docs:
        doc["image_url"] = find_image_for_query(doc.get("source_title", ""))
        
    return {
        "documents": docs,
        "entities": entities,
        "is_emergency": check_emergency(query)
    }

@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "timestamp": time.time(), "version": "2.1"}

@app.post("/api/chat")
async def chat_endpoint(request: Request):
    # Rate limiting
    client_ip = request.client.host if request.client else "unknown"
    if not check_rate_limit(client_ip):
        async def rate_limit_stream():
            yield f"data: {json.dumps({'content': '⏳ **Rate limit reached.** Please wait a minute before sending another message. This protects the service for everyone! 💙'})}\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(rate_limit_stream(), media_type="text/event-stream")

    data = await request.json()
    message = data.get("message", "").strip()
    state = data.get("state", "National")
    history = data.get("history", []) # List of {"role": "user"|"assistant", "content": str}
    
    # Backend environment API key takes precedence
    api_key = DEEPSEEK_API_KEY or data.get("api_key", "").strip()
    model = data.get("model", "deepseek-chat") # deepseek-chat or deepseek-reasoner

    if not message:
        async def empty_stream():
            msg = json.dumps({"content": "💡 **Hmm, looks like an empty message!** Try asking about MND equipment, NDIS funding, or care planning — I'm here to help! 🌟"})
            yield f"data: {msg}\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(empty_stream(), media_type="text/event-stream")

    # Enforce max message length (2000 chars)
    if len(message) > 2000:
        message = message[:2000]

    # Run Prompt Injection & Security Guardrail Check
    guard_res = sanitize_input(message)
    if not guard_res["is_safe"]:
        async def guard_stream():
            warning_msg = f"🛡️ **Security Guardrail Triggered:** {guard_res['flag_reason']}. Please ask a standard question about MND care, equipment, NDIS, or support services."
            yield f"data: {json.dumps({'content': warning_msg})}\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(guard_stream(), media_type="text/event-stream")

    is_emergency = check_emergency(message)
    
    # Perform RAG retrieval with strict state filtering
    docs = indexer.search_documents(message, state=state, top_k=5)
    entities = indexer.search_entities(message, state=state, top_k=4)

    # Attach images if found
    for ent in entities:
        ent["image_url"] = find_image_for_query(ent.get("name", ""))
    for doc in docs:
        doc["image_url"] = find_image_for_query(doc.get("source_title", ""))

    # Format context block
    context_items = []
    
    if entities:
        context_items.append(f"=== STRUCTURED ENTITY & DIRECTORY RECORDS (FILTERED FOR {state.upper()}) ===")
        for ent in entities:
            ent_str = f"• Name: {ent.get('name')}\n  Category: {ent.get('category')}\n  State: {ent.get('state')}\n  Description: {ent.get('description')}\n  Eligibility/Notes: {ent.get('eligibility', '') or ent.get('funding_notes', '')}\n  Website/URL: {ent.get('website', '') or ent.get('source_url', '') or ent.get('product_url', '')}"
            if ent.get("image_url"):
                ent_str += f"\n  Image URL: {ent.get('image_url')}"
            context_items.append(ent_str)

    if docs:
        context_items.append(f"\n=== RETRIEVED DOCUMENT CHUNKS (FILTERED FOR {state.upper()}) ===")
        for d in docs:
            d_str = f"• Title: {d.get('source_title')} (Publisher: {d.get('publisher')}, State: {d.get('state')})\n  URL: {d.get('url')}\n  Content: {d.get('text')}"
            if d.get("image_url"):
                d_str += f"\n  Image URL: {d.get('image_url')}"
            context_items.append(d_str)

    context_block = "\n\n".join(context_items)
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(selected_state=state, context_block=context_block)

    emergency_banner = ""
    if is_emergency:
        emergency_banner = "🚨 **EMERGENCY WARNING:** If you or someone you are caring for is experiencing acute, severe breathing difficulty, choking, or a sudden emergency, **PLEASE CALL TRIPLE ZERO (000) IMMEDIATELY** for an ambulance in Australia.\n\n"

    # DeepSeek API Call streaming OR Offline Fallback RAG generator
    if api_key:
        # Stream response from DeepSeek API with conversation history
        async def deepseek_stream_generator():
            if emergency_banner:
                yield f"data: {json.dumps({'content': emergency_banner})}\n\n"

            url = "https://api.deepseek.com/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
            # Construct message sequence with system prompt + trimmed history + latest query
            api_messages = [{"role": "system", "content": system_prompt}]
            
            # Append sanitized recent history (max 6 items)
            if isinstance(history, list):
                for item in history[-6:]:
                    if isinstance(item, dict) and "role" in item and "content" in item:
                        r = "user" if item["role"] == "user" else "assistant"
                        api_messages.append({"role": r, "content": str(item["content"])[:1000]})
            
            user_prompt_with_state = f"[Target Region: {state}]\nQuery: {message}"
            api_messages.append({"role": "user", "content": user_prompt_with_state})

            payload = {
                "model": model,
                "messages": api_messages,
                "stream": True,
                "temperature": 0.3
            }

            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    async with client.stream("POST", url, headers=headers, json=payload) as response:
                        if response.status_code != 200:
                            err_text = await response.aread()
                            yield f"data: {json.dumps({'content': f'⚠️ DeepSeek API Error ({response.status_code}): {err_text.decode()}'})}\n\n"
                            return
                        
                        async for chunk in response.aiter_lines():
                            if chunk.startswith("data: "):
                                data_str = chunk[6:]
                                if data_str.strip() == "[DONE]":
                                    break
                                try:
                                    parsed = json.loads(data_str)
                                    delta = parsed["choices"][0]["delta"].get("content", "")
                                    if delta:
                                        yield f"data: {json.dumps({'content': delta})}\n\n"
                                except Exception:
                                    pass
            except Exception as e:
                yield f"data: {json.dumps({'content': f'⚠️ Connection Error: {str(e)}'})}\n\n"

            yield "data: [DONE]\n\n"

        return StreamingResponse(deepseek_stream_generator(), media_type="text/event-stream")

    else:
        # Instant Offline RAG Synthesizer when no DeepSeek API key is entered yet
        async def offline_stream_generator():
            await asyncio.sleep(0.1)
            
            if emergency_banner:
                yield f"data: {json.dumps({'content': emergency_banner})}\n\n"

            intro = f"*(Using Local Knowledge Index Mode — Enter a DeepSeek API key in the top right to enable live DeepSeek API generation)*\n\n"
            yield f"data: {json.dumps({'content': intro})}\n\n"

            # Build intelligent local synthesis response from top entities & docs
            response_text = f"### G'day! ✨ Here is what we found for: \"{message}\"\n\n"
            if state and state != "National":
                response_text += f"🌟 *Tailored specifically for our friends in **{state}**!*\n\n"

            if entities:
                response_text += "#### 🚀 Awesome Services & Equipment Pathways:\n"
                for ent in entities:
                    url = ent.get('website') or ent.get('source_url') or ent.get('product_url') or '#'
                    response_text += f"- **[{ent.get('name')}]({url})** ✨ ({ent.get('category', '').replace('_', ' ').title()})\n  {ent.get('description')}\n"
                    if ent.get('eligibility'):
                        response_text += f"  *Who's eligible:* {ent.get('eligibility')}\n"
                    if ent.get('image_url'):
                        response_text += f"  \n  ![{ent.get('name')}]({ent.get('image_url')})\n\n"
                    response_text += "\n"

            if docs:
                response_text += "#### 💡 Top Care & Knowledge Insights:\n"
                for doc in docs[:3]:
                    response_text += f"**From [{doc.get('source_title')}]({doc.get('url')})** *(Publisher: {doc.get('publisher')})*:\n"
                    txt_snippet = doc.get('text', '')
                    if len(txt_snippet) > 300:
                        txt_snippet = txt_snippet[:300] + "..."
                    response_text += f"> \"{txt_snippet}\"\n\n"

            # Build explicit clickable sources section
            response_text += "### 📚 Verified Sources & Reference Links:\n"
            seen_urls = set()
            if entities:
                for ent in entities:
                    url = ent.get('website') or ent.get('source_url') or ent.get('product_url')
                    name = ent.get('name')
                    if url and url not in seen_urls and url != '#':
                        seen_urls.add(url)
                        response_text += f"- 🔗 [{name}]({url}) *(Structured Directory Record)*\n"
            if docs:
                for doc in docs:
                    url = doc.get('url')
                    title = doc.get('source_title')
                    pub = doc.get('publisher')
                    if url and url not in seen_urls and url:
                        seen_urls.add(url)
                        response_text += f"- 🔗 [{title} — {pub}]({url})\n"

            response_text += "\n---\n*💙 Remember, your MND care team (your MND advisor, OT, speech pathologist & GP) is always your best squad to guide personal care decisions!*"

            # Stream chunks for smooth typing effect
            words = response_text.split(" ")
            for i in range(0, len(words), 4):
                chunk_words = " ".join(words[i:i+4]) + " "
                yield f"data: {json.dumps({'content': chunk_words})}\n\n"
                await asyncio.sleep(0.02)

            yield "data: [DONE]\n\n"

        return StreamingResponse(offline_stream_generator(), media_type="text/event-stream")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
