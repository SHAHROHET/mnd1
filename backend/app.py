import sys
import os
import json
import asyncio
import re
import time
import random
from contextlib import asynccontextmanager
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
from answer_policy import (
    classify_query,
    collect_sources,
    public_sources,
    refine_sources,
    should_include_resource_images,
    is_emergency as check_emergency,
    answer_guidance,
    audience_guidance,
    length_guidance,
    topic_guidance,
    situation_logic,
    build_offline_answer,
    strip_verified_sources_section,
    CRISIS_BANNER,
    EMERGENCY_BANNER,
)

indexer = MNDIndexer()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    indexer.load_index()
    build_image_map()
    yield


app = FastAPI(title="Australian MND Assistant API", version="2.1", lifespan=lifespan)

# In-memory rate limiter: max requests per 60 seconds per IP with memory leak prevention
RATE_LIMIT_WINDOW = 60  # seconds
RATE_LIMIT_MAX = int(os.getenv("MND_RATE_LIMIT_MAX", "30"))
_rate_store: dict[str, list[float]] = defaultdict(list)
ALLOWED_STATES = {"National", "NSW", "VIC", "QLD", "WA", "SA", "TAS", "ACT", "NT"}


def normalize_state(value: str | None) -> str:
    """Return a supported Australian state/territory selector."""
    state = str(value or "National").strip().upper()
    if state == "NATIONAL":
        return "National"
    return state if state in ALLOWED_STATES else "National"


def cors_origins_from_env() -> list[str]:
    raw = os.getenv("MND_ALLOWED_ORIGINS", "").strip()
    if raw:
        return [origin.strip() for origin in raw.split(",") if origin.strip()]
    return [
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

def check_rate_limit(client_ip: str) -> bool:
    """Returns True if request is allowed, False if rate limited. Prunes stale IPs to prevent unbounded memory growth."""
    now = time.time()
    window_start = now - RATE_LIMIT_WINDOW
    # Prune old entries for this client
    _rate_store[client_ip] = [t for t in _rate_store[client_ip] if t > window_start]
    # Periodic global cleanup when store grows large
    if len(_rate_store) > 5000:
        stale_keys = [ip for ip, timestamps in _rate_store.items() if not timestamps or timestamps[-1] < window_start]
        for ip in stale_keys:
            del _rate_store[ip]
    if len(_rate_store[client_ip]) >= RATE_LIMIT_MAX:
        return False
    _rate_store[client_ip].append(now)
    return True

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com https://fonts.googleapis.com; "
        "font-src 'self' https://cdnjs.cloudflare.com https://fonts.gstatic.com; "
        "img-src 'self' data: https:; "
        "connect-src 'self' https://api.deepseek.com; "
        "frame-ancestors 'self';"
    )
    return response

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins_from_env(),
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
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

os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

IMAGES_DIR = os.path.join(BASE_DIR, "images")
if os.path.exists(IMAGES_DIR):
    app.mount("/images", StaticFiles(directory=IMAGES_DIR), name="images")

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

SYSTEM_PROMPT_TEMPLATE = """You are the Australian MND/ALS Care Assistant. You provide clear, structured, and clinically logical guidance to people living with Motor Neurone Disease (MND/ALS), their family carers, and healthcare clinicians across Australia.

Core Logical Principles:
- Grounding: Answer accurately from the retrieved context below. Do not invent non-existent services, dollar figures, or unverified clinical claims.
- Clinical & Practical Reasoning: Break answers down logically into:
  1. Direct Summary: Direct, authoritative answer addressing the user's specific situation.
  2. Options & Pathways: Specific assistive technology, clinical interventions, or funding programs.
  3. Step-by-Step Access Logic: The sequential process to follow (e.g. Clinical Assessment -> Funding/Scheme Route -> Sourcing/Trial -> Home Setup).
  4. Practical Considerations & Precautions: Important safety, progression, or carer workload factors.
  5. Questions for Your Care Team: 2-3 specific, high-yield questions for the user's next appointment.
- Structure & Readability: Use clear markdown headings (###), bold key terms, and bullet points for effortless scannability. Avoid dense walls of text.
- Separation of Sources: Do NOT generate a "Verified Sources" heading or bullet list of links in your text body; sources are automatically rendered by the user interface.
- Organisation Names: Use readable Australian organisation names (e.g. MND Australia, FlexEquip, EnableNSW, Carer Gateway, Services Australia) rather than raw filenames.
- Tone: Empathetic, dignified, practical, and objective. Never offer false hope or unverified cure claims.

{audience_guidance}
{answer_guidance}
{length_guidance}
{topic_guidance}

{situation_logic}

Images:
Embed an image only when the question is about equipment or home aids AND the context includes an Image URL. Use `![Short caption](image_url)` on its own line. Use the exact relative path. Never add images for grief, mental health, prognosis, diagnosis, or funding-only questions.

Location:
The user selected **{selected_state}**. Frame all equipment, funding, and support pathways around {selected_state}:
- NSW / ACT: FlexEquip (MND NSW), EnableNSW Equipment Allocation Program, MND NSW Support Services
- VIC: State-Wide Equipment Program (SWEP), MND Victoria Equipment Service & Support Coordinators
- QLD: Medical Aids, Subsidy Scheme (MASS), MND Queensland Equipment Library
- WA: MND Western Australia Assistive Technology Library & Care Advisors
- SA / NT: MND South Australia Equipment Service & Regional Advisors
- TAS: MND Victoria (TAS service delivery) & Community Equipment Scheme (CES)

Retrieved context:
{context_block}
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
        "missing_source_urls": indexer.missing_url_count(),
        "status": "online"
    }

@app.get("/api/images")
async def get_images_map():
    return IMAGE_MAP

@app.post("/api/search", include_in_schema=False)
async def search_endpoint(payload: dict):
    query = str(payload.get("query", "")).strip()
    state = normalize_state(payload.get("state"))
    if not query:
        raise HTTPException(status_code=400, detail="Query string is required")

    guard_res = sanitize_input(query)
    if not guard_res["is_safe"]:
        raise HTTPException(status_code=400, detail=guard_res["flag_reason"])
    query = guard_res["sanitized_text"][:2000]
    policy = classify_query(query)
        
    docs = indexer.search_documents(query, state=state, top_k=5, topic=policy["topic"])
    entities = indexer.search_entities(query, state=state, top_k=4, topic=policy["topic"])
    
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
            yield f"data: {json.dumps({'content': 'Too many messages in a short time. Please wait a minute and try again.'})}\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(rate_limit_stream(), media_type="text/event-stream")

    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    message = str(data.get("message", "")).strip()
    state = normalize_state(data.get("state"))
    history = data.get("history", []) # List of {"role": "user"|"assistant", "content": str}
    profile_prompt = build_user_profile_system_prompt(data.get("profile"))
    profile_role = None
    raw_profile = data.get("profile") if isinstance(data.get("profile"), dict) else {}
    if raw_profile.get("role") in ALLOWED_PROFILE_ROLES:
        profile_role = raw_profile.get("role")
    
    # Backend environment API key only — never accept a key from the browser
    api_key = DEEPSEEK_API_KEY
    model = "deepseek-chat"

    if not message:
        async def empty_stream():
            msg = json.dumps({"content": "Please type a question about MND care, equipment, NDIS, or support."})
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
    message = guard_res["sanitized_text"]
    policy = classify_query(message, profile_role)

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

    # Conversation history and follow-up expansion
    clean_history = []
    if isinstance(history, list):
        for item in history:
            if isinstance(item, dict) and "role" in item and "content" in item:
                role = "user" if item["role"] == "user" else "assistant"
                content = str(item["content"]).strip()[:2500]
                if not content:
                    continue
                history_guard = sanitize_input(content)
                if history_guard["is_safe"]:
                    clean_history.append({
                        "role": role,
                        "content": history_guard["sanitized_text"][:2500],
                    })

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
    # Retrieve more excerpts when the answer needs a detailed pathway
    doc_k = 8 if policy.get("detail_mode") == "detailed" else 5
    ent_k = 6 if policy.get("detail_mode") == "detailed" else 4
    docs = indexer.search_documents(search_query, state=state, top_k=doc_k, topic=policy["topic"])
    entities = indexer.search_entities(search_query, state=state, top_k=ent_k, topic=policy["topic"])

    # Attach product photos to visual equipment entities only — skip
    # category fallback so NIV/info records are not paired with unrelated beds.
    policy["show_images"] = should_include_resource_images(search_query)
    if policy["show_images"]:
        for ent in entities:
            ent["image_url"] = find_image_for_query(ent.get("name", ""))

    packaged_sources = collect_sources(docs, entities)
    if data.get("debug"):
        sources = refine_sources(packaged_sources, search_query, policy["topic"])
    else:
        sources = refine_sources(public_sources(packaged_sources), search_query, policy["topic"])

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

    context_block = "\n\n".join(context_items) or "No matching knowledge-base excerpts were found for this question."
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        selected_state=state,
        context_block=context_block,
        answer_guidance=answer_guidance(policy, state),
        audience_guidance=audience_guidance(policy["audience"]),
        length_guidance=length_guidance(policy["length_mode"]),
        topic_guidance=topic_guidance(policy["topic"]),
        situation_logic=situation_logic(policy, state, message),
    )
    if profile_prompt:
        system_prompt = f"{profile_prompt}\n\n{system_prompt}"

    emergency_banner = ""
    if policy["emergency"]:
        emergency_banner = EMERGENCY_BANNER
    elif policy["crisis"]:
        emergency_banner = CRISIS_BANNER

    # DeepSeek API Call streaming OR Offline Fallback RAG generator
    if api_key:
        # Stream response from DeepSeek API with conversation history
        async def deepseek_stream_generator():
            if emergency_banner:
                yield f"data: {json.dumps({'content': emergency_banner})}\n\n"

            if sources:
                yield f"data: {json.dumps({'sources': sources})}\n\n"

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
            user_prompt_parts.append(situation_logic(policy, state, message))
            user_prompt_parts.append(f"Question: {message}")
            user_prompt_parts.append(
                "Write the full answer now. Follow the situation logic. "
                "Be detailed enough to act on this week, with short paragraphs and bullets."
            )
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
                            yield f"data: {json.dumps({'content': f'The assistant service returned an error ({response.status_code}). Please try again shortly.'})}\n\n"
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
            except Exception:
                yield f"data: {json.dumps({'content': 'Could not reach the assistant service. Please try again.'})}\n\n"

            yield "data: [DONE]\n\n"

        return StreamingResponse(deepseek_stream_generator(), media_type="text/event-stream")

    else:
        # Instant offline answers when no API key is configured
        async def offline_stream_generator():
            await asyncio.sleep(0.1)
            
            if emergency_banner:
                yield f"data: {json.dumps({'content': emergency_banner})}\n\n"

            if sources:
                yield f"data: {json.dumps({'sources': sources})}\n\n"

            response_text = build_offline_answer(policy, entities, docs)
            checked = validate_output(response_text)
            response_text = strip_verified_sources_section(checked.get("cleaned_text") or response_text)

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
