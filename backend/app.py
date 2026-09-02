import sys
import os
import json
import asyncio
import re
import time
import random
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

IMAGE_MATCH_STOPWORDS = {
    "and", "the", "for", "with", "from", "mnd", "care", "home", "program",
    "aged", "australia", "illustration", "support", "guidance",
}

def find_image_for_query(query: str) -> str:
    """Match a query string against IMAGE_MAP keys using token-level scoring."""
    norm_query = re.sub(r'[^a-z0-9]', '', query.lower())
    if not norm_query:
        return ""
    # Exact match
    if norm_query in IMAGE_MAP:
        return IMAGE_MAP[norm_query]
    # Substring match only when both sides are specific enough to avoid
    # generic tokens like "and" matching a bed product photo.
    for key, path in IMAGE_MAP.items():
        shorter, longer = (key, norm_query) if len(key) <= len(norm_query) else (norm_query, key)
        if len(shorter) >= 12 and shorter in longer:
            return path
    # Token-level matching: split query into tokens and score against each key
    query_tokens = {
        tok for tok in re.findall(r'[a-z0-9]{3,}', query.lower())
        if tok not in IMAGE_MATCH_STOPWORDS
    }
    if not query_tokens:
        return ""
    best_path = ""
    best_score = 0
    for key, path in IMAGE_MAP.items():
        matched = sum(1 for tok in query_tokens if tok in key)
        if matched > best_score:
            best_score = matched
            best_path = path
    # Require at least 2 matching tokens, or 1 if query had only 1 token
    min_required = 1 if len(query_tokens) <= 1 else 2
    return best_path if best_score >= min_required else ""

VISUAL_RESOURCE_TERMS = {
    "aac", "bed", "beds", "chair", "chairs", "commode", "commodes", "cough",
    "cushion", "device", "devices", "equipment", "hoist", "hoists", "lift",
    "lifter", "mobility", "mount", "nebuliser", "niv", "peg", "ramp", "rollator",
    "scooter", "shower", "sling", "toilet", "transfer", "ventilator", "walker",
    "wheelchair", "wheelchairs",
}

def should_include_resource_images(query: str) -> bool:
    words = set(re.findall(r"[a-z0-9]+", str(query).lower()))
    joined = " ".join(words)
    return bool(words & VISUAL_RESOURCE_TERMS) or "cough assist" in joined or "eye gaze" in joined

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

# Greeting fast-path: patterns and randomized responses
GREETING_PATTERNS = re.compile(
    r'^(hi|hello|hey|gday|g\'day|howdy|yo|hiya|sup|heya|'
    r'hi there|hello there|hey there|'
    r'good morning|good afternoon|good evening|good night|'
    r'how are you|how are you doing|how are you going|'
    r'how r u|hru|whats up(?: mate)?|what\'s up(?: mate)?|wassup(?: mate)?|'
    r'how do you do|nice to meet you|'
    r'thanks|thank you|cheers|ta)$'
)

GREETING_RESPONSES = [
    "Hello. I am the MND Care Assistant. Ask about equipment, NDIS, breathing support, or carer services and I will point you to verified Australian sources.",
    "Hi — thanks for getting in touch. I can help with MND equipment pathways, funding, and local support. What would you like to know?",
    "Hello. I am ready to help with care planning, assistive technology, and state-specific MND services. How can I assist today?",
    "Hi. I can explain NDIS and equipment options, breathing support, and carer payments using verified Australian guidance. What do you need?",
    "Hello. Tell me what you need help with — equipment loans, NDIS, respiratory care, or carer support — and I will keep the answer practical and sourced.",
]

ALLOWED_PROFILE_GENDERS = {"Male", "Female", "Non-binary", "Other"}
ALLOWED_PROFILE_ROLES = {
    "Disability Support Worker",
    "Carer",
    "Physiotherapist",
    "Occupational Therapist",
    "Client/Participant",
    "Other",
}
ALLOWED_PROFILE_LOCATIONS = {"NSW", "VIC", "QLD", "WA", "SA", "TAS", "ACT", "NT"}

def build_user_profile_system_prompt(profile: dict | None) -> str | None:
    if not isinstance(profile, dict):
        return None

    try:
        age = int(profile.get("age"))
    except (TypeError, ValueError):
        return None

    gender = str(profile.get("gender", "")).strip()
    role = str(profile.get("role", "")).strip()
    location = str(profile.get("location", "")).strip().upper()

    if age < 1 or age > 120:
        return None
    if gender not in ALLOWED_PROFILE_GENDERS:
        return None
    if role not in ALLOWED_PROFILE_ROLES:
        return None
    if location not in ALLOWED_PROFILE_LOCATIONS:
        return None

    return (
        f"The user is a {age} year old {gender}, with the role {role}, "
        f"based in {location}, Australia. Tailor your legal, medical, and "
        "practical advice strictly to their jurisdiction and professional scope."
    )

SYSTEM_PROMPT_TEMPLATE = """You are the Australian MND/ALS Care Assistant. You help people living with Motor Neurone Disease (MND/ALS), their carers, families, and clinicians across Australia.

Tone:
- Calm, clear, and professional. Be warm without being playful or salesy.
- Use plain English, short paragraphs, and bullet lists. Prefer headings over decoration.
- Do not fill answers with emojis. At most one emoji in a whole reply, and only if it adds meaning.
- Do not open with a catchphrase on every answer. Start with the useful information.
- Stay accurate on NDIS, equipment loan schemes (FlexEquip, SWEP, MASS, EnableNSW), and clinical guidance. If something depends on an assessment, say so.
- Small talk: reply in 1-2 short sentences. Do not attach source lists or equipment recommendations unless asked.
- Identity questions: use the saved user profile when provided. If none exists, explain they can open **My Profile** in the sidebar.

Images:
When recommending a specific piece of equipment and the retrieved context includes an Image URL, embed it on its own line as `![Item Name](image_url)`. Use the exact relative path. Do not prepend a domain.

Location:
The user selected **{selected_state}**. Tailor funding schemes, loan libraries, and associations to that jurisdiction:
- NSW or ACT: FlexEquip, MND NSW, EnableNSW
- VIC: SWEP, MND Victoria
- QLD: MASS, MND Queensland
- WA: MND Western Australia and WA Health pathways
- SA: MND South Australia and SA Health pathways
- Weave state details into the answer. Do not use a fixed opening template.

Retrieved context:
{context_block}

Required closing section — never omit:
### Verified Sources & Reference Links
List every source used from the context as its own bullet:
- [Source Title — Publisher Name](exact_url)
Never join multiple links on one line. Do not add a second sources heading or a visual card deck.
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

@app.get("/api/images")
async def get_images_map():
    return IMAGE_MAP

@app.post("/api/search")
async def search_endpoint(payload: dict):
    query = payload.get("query", "")
    state = payload.get("state", "National")
    if not query:
        raise HTTPException(status_code=400, detail="Query string is required")
        
    docs = indexer.search_documents(query, state=state, top_k=5)
    entities = indexer.search_entities(query, state=state, top_k=4)
    
    # Attach images only when the user is clearly asking about visual equipment/resources.
    if should_include_resource_images(query):
        for ent in entities:
            ent["image_url"] = find_image_for_query(ent.get("name", ""))
        
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
    profile_prompt = build_user_profile_system_prompt(data.get("profile"))
    
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
            warning_msg = f"**Request blocked:** {guard_res['flag_reason']}. Please ask a standard question about MND care, equipment, NDIS, or support services."
            yield f"data: {json.dumps({'content': warning_msg})}\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(guard_stream(), media_type="text/event-stream")

    # Fast-path for casual greetings — skip RAG + LLM entirely to save API tokens
    clean_msg = re.sub(r'[^a-z\'\s]', '', message.lower()).strip(" '")
    if GREETING_PATTERNS.match(clean_msg):
        async def greeting_stream():
            greeting_text = random.choice(GREETING_RESPONSES)
            if state and state != "National":
                greeting_text = greeting_text.rstrip(".!") + f" I can tailor this for **{state}**."
            yield f"data: {json.dumps({'content': greeting_text})}\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(greeting_stream(), media_type="text/event-stream")

    # Fast-path for user identity & assistant identity questions
    if re.match(r'^(who am i|who am i\?|who is this|what is my role|what is my profile|my profile)$', clean_msg):
        async def identity_stream():
            if profile_prompt:
                reply = (
                    "Based on your saved profile:\n\n"
                    f"{profile_prompt}\n\n"
                    "Ask about MND equipment, NDIS pathways, symptom support, or local services for your role."
                )
            else:
                reply = (
                    "You haven't set up a personal profile yet.\n\n"
                    "Open **My Profile** in the sidebar to save your age, role "
                    "(such as Carer, OT, Physiotherapist, or person living with MND), "
                    "and Australian state so answers can be tailored."
                )
            yield f"data: {json.dumps({'content': reply})}\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(identity_stream(), media_type="text/event-stream")

    if re.match(r'^(who are you|who are you\?|what are you|what can you do|what do you do|help me|about you)$', clean_msg):
        async def bot_identity_stream():
            reply = (
                "I am the **Australian MND/ALS Care Assistant**, a knowledge guide for people living with Motor Neurone Disease, family carers, occupational therapists, and clinical teams in Australia.\n\n"
                "I can help with:\n"
                "- **Assistive equipment:** FlexEquip, SWEP, MASS, and EnableNSW loan programs\n"
                "- **NDIS and carer support:** planning, funding categories, and Centrelink payments\n"
                "- **Symptom support:** breathing, cough assist, speech/voice banking, and swallowing\n"
                "- **Local pathways:** MND Association advisors across NSW, VIC, QLD, WA, SA, TAS, ACT, and NT"
            )
            yield f"data: {json.dumps({'content': reply})}\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(bot_identity_stream(), media_type="text/event-stream")

    is_emergency = check_emergency(message)

    # Sanitize and validate conversation history
    clean_history = []
    if isinstance(history, list):
        for item in history:
            if isinstance(item, dict) and "role" in item and "content" in item:
                role = "user" if item["role"] == "user" else "assistant"
                content = str(item["content"]).strip()
                if content:
                    clean_history.append({"role": role, "content": content[:2500]})

    # Context-aware query expansion for follow-up questions
    # e.g. "summarize that in one sentence" or "show me a picture of that"
    search_query = message
    if clean_history:
        prev_user_queries = [m["content"] for m in clean_history if m["role"] == "user"]
        if prev_user_queries:
            last_user_query = prev_user_queries[-1]
            words = set(re.findall(r'[a-z0-9]+', message.lower()))
            follow_up_cues = {"that", "this", "it", "more", "summarize", "summary",
                              "sentence", "explain", "picture", "pictures", "options",
                              "option", "also", "instead", "why", "how", "above"}
            if len(message.split()) <= 7 or bool(words & follow_up_cues):
                search_query = f"{last_user_query} {message}"

    # Perform RAG retrieval with strict state filtering
    docs = indexer.search_documents(search_query, state=state, top_k=5)
    entities = indexer.search_entities(search_query, state=state, top_k=4)

    # Attach product photos to visual equipment entities only — skip
    # category fallback so NIV/info records are not paired with unrelated beds.
    if should_include_resource_images(search_query):
        for ent in entities:
            ent["image_url"] = find_image_for_query(ent.get("name", ""))

    # Format context block
    context_items = []
    
    if entities:
        context_items.append(f"=== STRUCTURED ENTITY & DIRECTORY RECORDS (FILTERED FOR {state.upper()}) ===")
        for ent in entities:
            ent_url = ent.get('url') or ent.get('website') or ent.get('source_url') or ent.get('served_url') or ent.get('product_url') or ''
            ent_str = f"• Name: {ent.get('name')}\n  Category: {ent.get('category')}\n  State: {ent.get('state')}\n  Description: {ent.get('description')}\n  Eligibility/Notes: {ent.get('eligibility', '') or ent.get('funding_notes', '')}\n  Website/URL: {ent_url}"
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
    if profile_prompt:
        system_prompt = f"{profile_prompt}\n\n{system_prompt}"

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
            
            # Construct message sequence with system prompt + conversation history + latest query
            api_messages = [{"role": "system", "content": system_prompt}]
            
            # Deduplicate: if the last history message IS the current user message, exclude it
            history_to_send = clean_history
            if (history_to_send and history_to_send[-1]["role"] == "user"
                    and history_to_send[-1]["content"] == message):
                history_to_send = history_to_send[:-1]

            # Append sanitized recent conversation turns (last 10 messages)
            for turn in history_to_send[-10:]:
                api_messages.append({"role": turn["role"], "content": turn["content"]})
            
            user_prompt_parts = [f"[Target Region: {state}]"]
            if profile_prompt:
                user_prompt_parts.append(f"[Saved User Profile: {profile_prompt}]")
                user_prompt_parts.append(
                    "Use the saved profile visibly: frame the answer for this user's role, "
                    "jurisdiction, and practical responsibilities."
                )
            user_prompt_parts.append(f"Query: {message}")
            user_prompt_with_state = "\n".join(user_prompt_parts)
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

            intro = (
                "*Local knowledge index — add a DeepSeek API key to enable live generated answers.*\n\n"
            )
            yield f"data: {json.dumps({'content': intro})}\n\n"

            # Build intelligent local synthesis response from top entities & docs
            response_text = ""
            if profile_prompt:
                response_text += f"**Profile used:** {profile_prompt}\n\n"

            if entities:
                response_text += "#### Services and equipment\n"
                for ent in entities:
                    url = ent.get('url') or ent.get('website') or ent.get('source_url') or ent.get('served_url') or ent.get('product_url') or '#'
                    response_text += f"- **[{ent.get('name')}]({url})** ({ent.get('category', '').replace('_', ' ').title()})\n  {ent.get('description')}\n"
                    if ent.get('eligibility'):
                        response_text += f"  *Who is eligible:* {ent.get('eligibility')}\n"
                    if ent.get('image_url'):
                        response_text += f"\n\n![{ent.get('name')}]({ent.get('image_url')})\n\n"
                    response_text += "\n"

            if docs:
                response_text += "#### From the knowledge base\n"
                for doc in docs[:3]:
                    response_text += f"**[{doc.get('source_title')}]({doc.get('url')})** *(Publisher: {doc.get('publisher')})*:\n"
                    txt_snippet = doc.get('text', '')
                    if len(txt_snippet) > 300:
                        txt_snippet = txt_snippet[:300] + "..."
                    response_text += f"> \"{txt_snippet}\"\n\n"

            # Build explicit clickable sources section
            response_text += "### Verified Sources & Reference Links:\n"
            seen_urls = set()
            if entities:
                for ent in entities:
                    url = ent.get('url') or ent.get('website') or ent.get('source_url') or ent.get('served_url') or ent.get('product_url')
                    name = ent.get('name')
                    if url and url not in seen_urls and url != '#':
                        seen_urls.add(url)
                        response_text += f"- [{name}]({url})\n"
            if docs:
                for doc in docs:
                    url = doc.get('url')
                    title = doc.get('source_title')
                    pub = doc.get('publisher')
                    if url and url not in seen_urls and url:
                        seen_urls.add(url)
                        response_text += f"- [{title} — {pub}]({url})\n"

            response_text += "\n---\n*Personal care decisions should be confirmed with your MND advisor, occupational therapist, speech pathologist, and GP.*"

            # Stream in larger chunks so markdown does not reflow on every word
            words = response_text.split(" ")
            for i in range(0, len(words), 16):
                chunk_words = " ".join(words[i:i+16]) + " "
                yield f"data: {json.dumps({'content': chunk_words})}\n\n"
                await asyncio.sleep(0.012)

            yield "data: [DONE]\n\n"

        return StreamingResponse(offline_stream_generator(), media_type="text/event-stream")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
