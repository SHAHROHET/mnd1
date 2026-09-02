import re

# --- Prompt Injection Detection Patterns ---
PROMPT_INJECTION_PATTERNS = [
    r"ignore\s+(?:all\s+)?(?:previous\s+instructions|safety\s+filters|guidelines)",
    r"override\s+(?:the\s+)?(?:system\s+prompt|safety\s+rules)",
    r"forget\s+(?:all\s+)?(?:your\s+)?(?:rules|instructions)",
    r"you\s+are\s+now\s+(?:dan|dav|evil|unrestricted)",
    r"(?:act|roleplay)\s+as\s+an?\s+(?:unrestricted|jailbroken|evil)",
    r"jailbreak",
    r"system\s*:\s*you\s+are",
    r"disregard\s+the\s+(?:above|previous)",
    r"pretend\s+you\s+(?:are|have)\s+no\s+(?:rules|restrictions|guidelines)",
    r"do\s+not\s+follow\s+(?:any|your)\s+(?:rules|instructions|guidelines)",
    r"respond\s+without\s+(?:any\s+)?(?:rules|restrictions|filters)",
    r"bypass\s+(?:all\s+)?(?:safety|content|system)\s+filters",
    r"(?:output|reveal|print|show)\s+(?:the|your)\s+(?:system\s+prompt|initialization\s+instructions|system\s+instructions)",
    r"developer\s+mode\s+(?:enabled|on|activate)",
    r"new\s+instructions?\s*:",
    r"\[system\]",
    r"\[\/system\]",
    r"\[inst\]",
    r"\[\/inst\]",
    r"<<sys>>",
    r"<</sys>>",
    r"<\|im_start\|>",
    r"<\|im_end\|>",
    r"<\|system\|>",
]

# Zero-width & directional override characters used for evasion
_EVASION_CHARS = re.compile(r'[\u200B-\u200D\uFEFF\u202A-\u202E\u2066-\u2069]')

# --- Output Safety Patterns ---
# These patterns catch potentially dangerous content in AI-generated responses
OUTPUT_DANGER_PATTERNS = [
    # Unsupported specific medication dosage claims
    (r"(?:take|administer|inject|prescribe)\s+\d+\s*(?:mg|ml|mcg|units?)\s+(?:of\s+)?(?:riluzole|edaravone|morphine|midazolam|fentanyl|oxycodone|diazepam|baclofen)",
     "Specific medication dosage recommendation detected — users must consult their prescribing physician"),
    # Fabricated Australian phone numbers (not real helplines)
    (r"(?:call|ring|phone|contact)\s+(?:0[23478]\d{8}|1[38]00\s?\d{3}\s?\d{3})",
     "Unverified phone number detected — cross-reference with official sources"),
    # Self-harm or euthanasia encouragement
    (r"(?:how\s+to\s+(?:end|take)\s+(?:your|my|one'?s?)\s+(?:own\s+)?life|suicide\s+method|assisted\s+(?:dying|suicide)\s+(?:steps|instructions|guide))",
     "Potentially harmful end-of-life content detected — refer to support services"),
]

# Verified Australian helpline numbers that should NOT be flagged
VERIFIED_NUMBERS = [
    "000",             # Triple Zero Emergency
    "1800 777 175",    # MND Australia Connect
    "1800 187 263",    # MND NSW InfoLine
    "1800 806 218",    # Beyond Blue (legacy)
    "1300 22 4636",    # Beyond Blue
    "1300224636",
    "131114",          # Lifeline
    "13 11 14",
    "1800 059 059",    # Carer Gateway (legacy)
    "1800 422 737",    # Carer Gateway
    "1800422737",
    "1800 800 110",    # NDIS
]

def sanitize_input(text: str) -> dict:
    """Scans user input for prompt injection and malicious control sequences."""
    if not text or not isinstance(text, str):
        return {"is_safe": True, "sanitized_text": "", "flag_reason": None}

    # Normalize by stripping zero-width and bidi override characters
    normalized = _EVASION_CHARS.sub("", text)
    text_clean = normalized.strip()
    
    # Reject absurdly long inputs (DoS prevention)
    if len(text_clean) > 5000:
        return {
            "is_safe": False,
            "sanitized_text": text_clean[:100] + "...",
            "flag_reason": "Security Notice: Message exceeds maximum allowed length (5000 characters)"
        }
    
    # Check for known prompt injection signatures
    for pattern in PROMPT_INJECTION_PATTERNS:
        if re.search(pattern, text_clean, re.IGNORECASE):
            return {
                "is_safe": False,
                "sanitized_text": text_clean,
                "flag_reason": "Security Notice: Input matched a restricted control pattern. Please rephrase your question about MND care."
            }

    return {
        "is_safe": True,
        "sanitized_text": text_clean,
        "flag_reason": None
    }

def validate_output(output_text: str) -> dict:
    """Verifies that generated text complies with safety standards.
    
    Returns:
        dict with 'is_valid' (bool), 'flag_reason' (str or None), and
        'cleaned_text' (str) with any necessary safety disclaimers appended.
    """
    if not output_text or not isinstance(output_text, str):
        return {"is_valid": True, "flag_reason": None, "cleaned_text": output_text or ""}

    warnings = []
    
    for pattern, reason in OUTPUT_DANGER_PATTERNS:
        if re.search(pattern, output_text, re.IGNORECASE):
            warnings.append(reason)

    if warnings:
        disclaimer = "\n\n> ⚠️ **Safety Notice:** " + "; ".join(warnings) + ". Always consult your treating MND clinical team for personalised medical advice."
        return {
            "is_valid": False,
            "flag_reason": "; ".join(warnings),
            "cleaned_text": output_text + disclaimer
        }

    return {"is_valid": True, "flag_reason": None, "cleaned_text": output_text}
