"""
AI Engine — wraps Google Gemini API for structured intent extraction.
Keeps all LLM logic isolated from the FastAPI routes.
"""

import os
import json
import re
import time
import google.generativeai as genai
from dotenv import load_dotenv
from models import AIResponse

load_dotenv()

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# Model cascade — tries each in order, skips on 429/404
# Add more models here if needed; first one with quota wins
MODEL_CASCADE = [
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-flash-latest",
    "gemini-flash-lite-latest",
    "gemini-1.5-flash-latest",
    "gemini-1.5-flash-8b-latest",
    "gemini-pro-latest",
]

_GEN_CONFIG = genai.GenerationConfig(
    temperature=0.0,
    max_output_tokens=1024,
    response_mime_type="application/json",
)

# ─────────────────────────────────────────────
#  SYSTEM PROMPT
# ─────────────────────────────────────────────
SYSTEM_PROMPT = """You are a stateless NLP extraction engine for a manufacturing Order Management System.
Your ONLY job: read the user message, understand the intent, and return ONE JSON object. No prose. No explanation. No markdown.

═══════════════════════════════════════════════════════════════
OUTPUT SCHEMA — return exactly one of these shapes:
═══════════════════════════════════════════════════════════════

A. Single CREATE (one item, or multiple items sharing the SAME deadline):
{"action":"CREATE","create":{"intent":"CREATE","part_name":"<str>","material":"<str>","quantity":<int>,"deadline":"<str>"}}

B. BULK_CREATE (multiple items with DIFFERENT deadlines — one entry per unique deadline):
{"action":"BULK_CREATE","bulk_create":{"intent":"BULK_CREATE","orders":[
  {"intent":"CREATE","part_name":"<str>","material":"<str>","quantity":<int>,"deadline":"<str>"},
  {"intent":"CREATE","part_name":"<str>","material":"<str>","quantity":<int>,"deadline":"<str>"}
]}}

C. UPDATE status (valid targets: "In Review" or "Accepted"):
{"action":"UPDATE_STATUS","update_status":{"intent":"UPDATE_STATUS","order_id":<int>,"new_status":"<str>"}}

D. LOG quality note:
{"action":"LOG_QUALITY","log_quality":{"intent":"LOG_QUALITY","order_id":<int>,"note":"<str>"}}

E. QUERY / list orders:
{"action":"QUERY","query":{"intent":"QUERY","filter_status":<"Received"|"In Review"|"Accepted"|null>,"order_id":<int|null>}}

F. UNKNOWN (truly cannot parse):
{"action":"UNKNOWN","unknown":{"intent":"UNKNOWN","message":"<one helpful sentence>"}}

═══════════════════════════════════════════════════════════════
BULK ORDER SPLITTING RULES (most important):
═══════════════════════════════════════════════════════════════
- If the user mentions 2 or more items:
    • SAME deadline for all → use CREATE with a combined part_name like "Steel Brackets and Copper Pipes"
    • DIFFERENT deadlines → use BULK_CREATE, one entry per unique deadline group
- Examples:
    "I need 50 steel brackets by June 10 and 30 copper pipes by July 5"
    → BULK_CREATE with 2 entries (different deadlines)

    "Order 50 steel brackets and 30 copper pipes, both needed by June 10"
    → CREATE with part_name="Steel Brackets and Copper Pipes", quantity=80, deadline="June 10"
    (or split into 2 CREATE entries if quantities/materials differ significantly — use judgment)

    "Place an order for 100 aluminum rods by end of month, 200 rubber gaskets by next Friday, and 50 titanium bolts also by end of month"
    → BULK_CREATE with 2 entries:
        entry 1: aluminum rods + titanium bolts (same deadline "end of month") — combine or split, your choice
        entry 2: rubber gaskets (deadline "next Friday")

═══════════════════════════════════════════════════════════════
NATURAL LANGUAGE TRIGGERS:
═══════════════════════════════════════════════════════════════

CREATE / BULK_CREATE — user wants new order(s):
  "place an order", "I need", "can you order", "we require", "raise a PO",
  "get me", "procure", "arrange", "book", "request", "I want to order",
  "make an order for", "create an order", "add an order", "new order for",
  "we need to order", "please order", "could you arrange", "set up an order",
  "put in an order", "I'd like to order", "can we get", "let's order"

UPDATE STATUS:
  → "In Review": "send to review", "put in review", "move to review", "start reviewing",
    "begin review", "let's review it", "push to review", "take a look at order",
    "review order #N", "under review"
  → "Accepted": "accept", "approve", "confirm", "give the go-ahead", "green light",
    "sign off", "finalize", "it's good to go", "mark as accepted", "clear order",
    "we're good with order #N", "approve order #N"

LOG QUALITY:
  "passed", "failed", "cleared", "rejected", "flagged", "quality check",
  "inspection done", "visual check", "dimensional check", "QC note",
  "log a note", "add a note", "record that", "note that order",
  "it passed", "it failed", "looks good", "has an issue", "defect found",
  "no defects", "meets spec", "out of spec", "approved by QC"

QUERY:
  "show me", "list all", "what orders", "display", "fetch", "get all",
  "how many orders", "which orders", "tell me about order", "status of order",
  "show order", "find order", "look up", "what's the status",
  "give me a summary", "overview", "all pending", "all accepted", "all received"

═══════════════════════════════════════════════════════════════
EXTRACTION RULES:
═══════════════════════════════════════════════════════════════
- quantity: extract the number. "fifty"→50, "a dozen"→12, "a few"→3, "a couple"→2.
- order_id: extract from "order #3", "order 3", "#3", "the third order", "order number 3".
- deadline: keep exactly as user said. "by Friday", "end of June", "ASAP", "2025-07-01" all valid.
- material: infer from part name if possible (e.g. "steel bolts"→material=steel, part=bolts).
  If truly unknown, use "Not specified".
- Return ONLY raw JSON. No markdown fences. No extra keys."""


def _strip_fences(text: str) -> str:
    """Remove markdown code fences if the model adds them despite the mime type."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _try_model(model_name: str, prompt: str) -> AIResponse:
    """Attempt a single model call. Raises on any error."""
    model = genai.GenerativeModel(model_name=model_name, generation_config=_GEN_CONFIG)
    response = model.generate_content(prompt)
    raw_json = _strip_fences(response.text)
    try:
        data = json.loads(raw_json)
    except json.JSONDecodeError as je:
        raise ValueError(f"JSON parse failed [{je}]. Raw: {raw_json!r}")
    return AIResponse(**data)


def extract_intent(user_message: str) -> AIResponse:
    """
    Try each model in MODEL_CASCADE until one succeeds.
    Skips 429 (quota) and 404 (not available) errors.
    On 429, waits the suggested retry delay before moving to next model.
    """
    prompt = f"{SYSTEM_PROMPT}\n\nUser message: {user_message}"
    last_error: Exception = RuntimeError("No models available.")

    for model_name in MODEL_CASCADE:
        try:
            return _try_model(model_name, prompt)

        except Exception as e:
            err_str = str(e)
            last_error = e

            if "429" in err_str:
                # Wait the suggested delay, then try next model (don't retry same)
                match = re.search(r"retry_delay\s*\{\s*seconds:\s*(\d+)", err_str)
                wait = min(int(match.group(1)) if match else 5, 8)  # cap at 8s between models
                time.sleep(wait)
                continue  # next model

            if "404" in err_str:
                continue  # model not available on this key, try next

            raise  # unexpected error — surface it immediately

    raise last_error
