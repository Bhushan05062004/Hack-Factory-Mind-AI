"""
Factory Mind AI — LLM Engine (Gemini API)
Hybrid architecture: regex rule engine first, then Gemini function-calling.

TOKEN-EFFICIENCY GUIDELINES:
- System prompt is static (~30 tokens) — never concatenated per request.
- Function-calling means LLM output is a tiny JSON (~30 tokens).
- RAG: top_k=3 for products, top_k=1 for SOPs; snippets trimmed to <=120/150 tokens.
- max_output_tokens=200 in the API call.
- For every new chat request, first run regex rule engine — if it succeeds, skip LLM (zero-token path).
- Log usage from the Gemini response and store cumulative totals; expose via /metrics.
"""

import os
import re
import json
import google.generativeai as genai
from dotenv import load_dotenv
from typing import Optional

from db import (
    create_order, get_order, update_order_status, log_quality,
    query_orders, cancel_order, log_usage, get_product_by_id,
)
from products import search_products
from sops import search_sops
from schemas import ChatResponse, UsageInfo
from utils import estimate_tokens, trim_to_tokens

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# Static system prompt — kept concise for token efficiency
SYSTEM_PROMPT = (
    "You are a manufacturing order assistant for Factory Mind AI. "
    "When a user wants to order or create an order:\n"
    "1. Look at the 'Relevant products from catalog' provided in the context.\n"
    "2. Find the product that matches their request.\n"
    "3. Extract the integer 'Product ID' from that matching product.\n"
    "4. Call the 'create_order' function with that product_id, the requested quantity, "
    "and a formatted deadline date (YYYY-MM-DD, estimating next week as today + 7 days if not specified).\n"
    "5. If the user asks for MULTIPLE different products, you MUST emit MULTIPLE 'create_order' function calls (one for each product).\n"
    "Always invoke function calls instead of replying in plain text when a tool is available."
)


# Model cascade — tries each in order, skips on 429/404.
# First model with available quota wins. Adapted from original ai_engine.py.
MODEL_CASCADE = [
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-3-flash-preview",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
]


# ─────────────────────────────────────────────
#  FUNCTION (TOOL) DECLARATIONS FOR GEMINI
# ─────────────────────────────────────────────
TOOL_DECLARATIONS = [
    genai.protos.Tool(function_declarations=[
        genai.protos.FunctionDeclaration(
            name="search_product_catalog",
            description="Retrieve the most relevant product(s) from the catalog based on a free-text query.",
            parameters=genai.protos.Schema(
                type=genai.protos.Type.OBJECT,
                properties={
                    "query": genai.protos.Schema(type=genai.protos.Type.STRING, description="User's free-text query about a product."),
                    "top_k": genai.protos.Schema(type=genai.protos.Type.INTEGER, description="How many product snippets to return. Default 3."),
                },
                required=["query"],
            ),
        ),
        genai.protos.FunctionDeclaration(
            name="search_sop",
            description="Find the most relevant SOP text for a given operational query.",
            parameters=genai.protos.Schema(
                type=genai.protos.Type.OBJECT,
                properties={
                    "query": genai.protos.Schema(type=genai.protos.Type.STRING, description="User's free-text query about a process or procedure."),
                    "top_k": genai.protos.Schema(type=genai.protos.Type.INTEGER, description="Number of SOP excerpts to return. Default 1."),
                },
                required=["query"],
            ),
        ),
        genai.protos.FunctionDeclaration(
            name="create_order",
            description="Create a new manufacturing order from a natural-language description.",
            parameters=genai.protos.Schema(
                type=genai.protos.Type.OBJECT,
                properties={
                    "product_id": genai.protos.Schema(type=genai.protos.Type.INTEGER, description="ID of the product selected from the catalog (must exist)."),
                    "quantity": genai.protos.Schema(type=genai.protos.Type.INTEGER, description="Number of units required."),
                    "deadline": genai.protos.Schema(type=genai.protos.Type.STRING, description="Requested delivery date (YYYY-MM-DD)."),
                    "notes": genai.protos.Schema(type=genai.protos.Type.STRING, description="Optional free-form note supplied by the user."),
                },
                required=["product_id", "quantity", "deadline"],
            ),
        ),
        genai.protos.FunctionDeclaration(
            name="update_status",
            description="Change the status of an existing order. Only operators can move to In Review or Accepted; users can only cancel within window.",
            parameters=genai.protos.Schema(
                type=genai.protos.Type.OBJECT,
                properties={
                    "order_id": genai.protos.Schema(type=genai.protos.Type.INTEGER, description="The order ID."),
                    "new_status": genai.protos.Schema(type=genai.protos.Type.STRING, description="Target status: In Review, Accepted, or Cancelled."),
                },
                required=["order_id", "new_status"],
            ),
        ),
        genai.protos.FunctionDeclaration(
            name="log_quality",
            description="Append a quality-inspection note to an order.",
            parameters=genai.protos.Schema(
                type=genai.protos.Type.OBJECT,
                properties={
                    "order_id": genai.protos.Schema(type=genai.protos.Type.INTEGER, description="The order ID."),
                    "note": genai.protos.Schema(type=genai.protos.Type.STRING, description="Free-form inspection result."),
                },
                required=["order_id", "note"],
            ),
        ),
        genai.protos.FunctionDeclaration(
            name="query_orders",
            description="Return a list of orders matching optional filters.",
            parameters=genai.protos.Schema(
                type=genai.protos.Type.OBJECT,
                properties={
                    "status": genai.protos.Schema(type=genai.protos.Type.STRING, description="Filter by status: Received, In Review, Accepted, Cancelled."),
                    "limit": genai.protos.Schema(type=genai.protos.Type.INTEGER, description="Maximum rows to return. Default 10."),
                },
                required=[],
            ),
        ),
    ])
]


# ─────────────────────────────────────────────
#  REGEX RULE ENGINE (zero-token path)
# ─────────────────────────────────────────────
def _try_regex_status_update(text: str, role: str) -> Optional[ChatResponse]:
    """Try to handle status updates via regex. Returns ChatResponse or None."""
    text_lower = text.lower()

    # Pattern: "order #42 accepted" / "accept order 42" / "move order #42 to in review"
    order_match = re.search(r"order\s*#?\s*(\d+)", text_lower)
    if not order_match:
        return None

    order_id = int(order_match.group(1))

    # Determine target status
    new_status = None
    if any(kw in text_lower for kw in ["accept", "approve", "confirm", "green light", "sign off", "finalize"]):
        new_status = "Accepted"
    elif any(kw in text_lower for kw in ["review", "in review", "reviewing"]):
        new_status = "In Review"
    elif any(kw in text_lower for kw in ["cancel"]):
        new_status = "Cancelled"

    if not new_status:
        return None

    # RBAC check
    if new_status in ("In Review", "Accepted") and role not in ("operator", "quality"):
        return ChatResponse(
            type="rule", name="update_status",
            message="⚠️ Only operators can update order status.",
            usage=UsageInfo(llm_used=False),
        )

    if new_status == "Cancelled":
        success, msg = cancel_order(order_id)
        return ChatResponse(
            type="rule", name="update_status",
            payload={"order_id": order_id, "new_status": new_status, "success": success},
            message=msg, usage=UsageInfo(llm_used=False),
        )

    order = get_order(order_id)
    if not order:
        return ChatResponse(
            type="rule", name="update_status",
            message=f"❌ Order #{order_id} not found.",
            usage=UsageInfo(llm_used=False),
        )

    old_status = order["status"]
    updated = update_order_status(order_id, new_status)
    return ChatResponse(
        type="rule", name="update_status",
        payload={"order_id": order_id, "old_status": old_status, "new_status": new_status},
        message=f"🔄 Order #{order_id} — Status updated: **{old_status}** → **{new_status}**",
        usage=UsageInfo(llm_used=False),
    )


def _try_regex_quality_log(text: str, role: str) -> Optional[ChatResponse]:
    """Try to handle quality log entries via regex. Returns ChatResponse or None."""
    text_lower = text.lower()

    quality_keywords = ["quality", "inspection", "passed", "failed", "defect", "qc", "visual check", "dimensional check"]
    if not any(kw in text_lower for kw in quality_keywords):
        return None

    order_match = re.search(r"order\s*#?\s*(\d+)", text_lower)
    if not order_match:
        return None

    if role not in ("operator", "quality"):
        return ChatResponse(
            type="rule", name="log_quality",
            message="⚠️ Only quality team members can log quality notes.",
            usage=UsageInfo(llm_used=False),
        )

    order_id = int(order_match.group(1))
    # Extract the note — everything after "order #N"
    note_start = order_match.end()
    note = text[note_start:].strip().lstrip("—–-:,").strip()
    if not note:
        note = text.strip()

    result = log_quality(order_id, note)
    if not result:
        return ChatResponse(
            type="rule", name="log_quality",
            message=f"❌ Order #{order_id} not found.",
            usage=UsageInfo(llm_used=False),
        )

    return ChatResponse(
        type="rule", name="log_quality",
        payload=result,
        message=f"📋 Quality note logged for Order #{order_id}: \"{note}\"",
        usage=UsageInfo(llm_used=False),
    )


def _try_regex_query(text: str, role: str, user_id: int) -> Optional[ChatResponse]:
    """Try to handle simple order queries via regex."""
    text_lower = text.lower()

    if not any(kw in text_lower for kw in ["show", "list", "display", "all orders", "my orders", "status of order", "what orders"]):
        return None

    # Check for specific order ID
    order_match = re.search(r"order\s*#?\s*(\d+)", text_lower)
    if order_match:
        order_id = int(order_match.group(1))
        order = get_order(order_id)
        if not order:
            return ChatResponse(
                type="rule", name="query_orders",
                message=f"❌ Order #{order_id} not found.",
                usage=UsageInfo(llm_used=False),
            )
        # RBAC filter
        if role == "user":
            order.pop("last_quality_note", None)
            order.pop("last_quality_ts", None)
            if order["status"] == "Accepted":
                return ChatResponse(
                    type="rule", name="query_orders",
                    message=f"❌ Order #{order_id} not found.",
                    usage=UsageInfo(llm_used=False),
                )
        return ChatResponse(
            type="rule", name="query_orders",
            payload={"orders": [order]},
            message=f"🔍 Order #{order['id']} — {order['part_name']} | {order['material']} | Qty: {order['quantity']} | Status: {order['status']}",
            usage=UsageInfo(llm_used=False),
        )

    # Filter by status
    status_filter = None
    for s in ["Received", "In Review", "Accepted", "Cancelled"]:
        if s.lower() in text_lower:
            status_filter = s
            break

    orders = query_orders(status=status_filter, limit=10, user_id=user_id, role=role)
    if not orders:
        return ChatResponse(
            type="rule", name="query_orders",
            payload={"orders": []},
            message="📭 No orders found.",
            usage=UsageInfo(llm_used=False),
        )

    lines = [f"📦 Showing {len(orders)} order(s):"]
    for o in orders:
        lines.append(f"  #{o['id']} | {o['part_name']} | Qty: {o['quantity']} | Status: {o['status']}")

    return ChatResponse(
        type="rule", name="query_orders",
        payload={"orders": orders},
        message="\n".join(lines),
        usage=UsageInfo(llm_used=False),
    )


# ─────────────────────────────────────────────
#  GEMINI FUNCTION DISPATCH
# ─────────────────────────────────────────────
def _dispatch_function(fn_name: str, fn_args: dict, role: str, user_id: int) -> ChatResponse:
    """Execute a function call returned by the LLM and return a ChatResponse."""

    if fn_name == "search_product_catalog":
        query = fn_args.get("query", "")
        top_k = fn_args.get("top_k", 3)
        results = search_products(query, k=top_k)
        if not results:
            msg = f"🔍 No products found matching \"{query}\"."
        else:
            lines = [f"🔍 Found {len(results)} matching product(s):"]
            for p in results:
                lines.append(f"  • **{p['name']}** ({p['material']}) — Part #{p['part_number']} [Score: {p['similarity_score']}]")
            msg = "\n".join(lines)
        return ChatResponse(type="function", name=fn_name, payload={"products": results}, message=msg)

    elif fn_name == "search_sop":
        query = fn_args.get("query", "")
        top_k = fn_args.get("top_k", 1)
        if role == "user":
            return ChatResponse(type="function", name=fn_name, message="⚠️ SOP details are only available to operators and quality staff.")
        results = search_sops(query, k=top_k)
        if not results:
            msg = f"📄 No SOPs found matching \"{query}\"."
        else:
            lines = [f"📄 Found {len(results)} SOP(s):"]
            for s in results:
                lines.append(f"  • **{s['title']}**\n    {s['snippet']}")
            msg = "\n".join(lines)
        return ChatResponse(type="function", name=fn_name, payload={"sops": results}, message=msg)

    elif fn_name == "create_order":
        if role != "user":
            return ChatResponse(type="function", name=fn_name, message="⚠️ Only users (stakeholders) can create orders.")
        product_id = fn_args.get("product_id")
        quantity = fn_args.get("quantity", 1)
        deadline = fn_args.get("deadline", "TBD")
        notes = fn_args.get("notes", "")

        product = get_product_by_id(product_id) if product_id else None
        part_name = product["name"] if product else f"Product #{product_id}"
        material = product["material"] if product else "Not specified"
        spec = product.get("specification", "") if product else ""

        order = create_order(
            user_id=user_id, part_name=part_name, quantity=quantity,
            deadline=deadline, material=material, specification=spec,
            notes=notes, product_id=product_id,
        )
        msg = (
            f"✅ Order #{order['id']} placed!\n"
            f"  • Part: **{part_name}**\n"
            f"  • Material: {material}\n"
            f"  • Quantity: {quantity}\n"
            f"  • Deadline: {deadline}\n"
            f"  • Status: **Received**\n"
            f"  • Cancellable until: {order['cancellable_until']}"
        )
        return ChatResponse(type="function", name=fn_name, payload=order, message=msg)

    elif fn_name == "update_status":
        order_id = fn_args.get("order_id")
        new_status = fn_args.get("new_status")
        if new_status == "Cancelled":
            success, msg = cancel_order(order_id)
            return ChatResponse(type="function", name=fn_name, payload={"order_id": order_id, "success": success}, message=msg)
        if new_status in ("In Review", "Accepted") and role not in ("operator", "quality"):
            return ChatResponse(type="function", name=fn_name, message="⚠️ Only operators can update order status.")
        order = get_order(order_id)
        if not order:
            return ChatResponse(type="function", name=fn_name, message=f"❌ Order #{order_id} not found.")
        old = order["status"]
        update_order_status(order_id, new_status)
        return ChatResponse(type="function", name=fn_name, payload={"order_id": order_id, "old_status": old, "new_status": new_status},
                            message=f"🔄 Order #{order_id}: **{old}** → **{new_status}**")

    elif fn_name == "log_quality":
        if role not in ("operator", "quality"):
            return ChatResponse(type="function", name=fn_name, message="⚠️ Only quality team can log quality notes.")
        order_id = fn_args.get("order_id")
        note = fn_args.get("note", "")
        result = log_quality(order_id, note, logged_by=user_id)
        if not result:
            return ChatResponse(type="function", name=fn_name, message=f"❌ Order #{order_id} not found.")
        return ChatResponse(type="function", name=fn_name, payload=result,
                            message=f"📋 Quality note logged for Order #{order_id}: \"{note}\"")

    elif fn_name == "query_orders":
        status_filter = fn_args.get("status")
        limit = fn_args.get("limit", 10)
        orders = query_orders(status=status_filter, limit=limit, user_id=user_id, role=role)
        if not orders:
            return ChatResponse(type="function", name=fn_name, payload={"orders": []}, message="📭 No orders found.")
        lines = [f"📦 {len(orders)} order(s):"]
        for o in orders:
            lines.append(f"  #{o['id']} | {o['part_name']} | Qty: {o['quantity']} | Status: {o['status']}")
        return ChatResponse(type="function", name=fn_name, payload={"orders": orders}, message="\n".join(lines))

    return ChatResponse(type="fallback", message=f"Unknown function: {fn_name}")


# ─────────────────────────────────────────────
#  GEMINI CALL WITH MODEL CASCADE
# ─────────────────────────────────────────────
def _call_gemini_with_cascade(full_prompt: str) -> tuple:
    """
    Try each model in MODEL_CASCADE until one succeeds.
    Skips 429 (quota exhausted) and 404 (model unavailable) errors.
    On 429, waits the suggested retry delay before trying the next model.
    Returns (response, model_name_used) or raises the last error.
    """
    import time

    last_error: Exception = RuntimeError("No models available.")

    for model_name in MODEL_CASCADE:
        try:
            model = genai.GenerativeModel(
                model_name=model_name,
                tools=TOOL_DECLARATIONS,
                system_instruction=SYSTEM_PROMPT,
                generation_config=genai.GenerationConfig(
                    temperature=0.0,
                    max_output_tokens=200,
                ),
            )
            response = model.generate_content(full_prompt)
            return response, model_name

        except Exception as e:
            err_str = str(e)
            last_error = e

            if "429" in err_str:
                # Wait the suggested delay, then try next model
                match = re.search(r"retry_delay\s*\{\s*seconds:\s*(\d+)", err_str)
                wait = min(int(match.group(1)) if match else 5, 8)
                time.sleep(wait)
                continue  # next model

            if "404" in err_str:
                continue  # model not available, try next

            raise  # unexpected error — surface immediately

    raise last_error


# ─────────────────────────────────────────────
#  MAIN ENTRY POINT
# ─────────────────────────────────────────────
def process_message(user_text: str, role: str, user_id: int) -> ChatResponse:
    """
    Main message processing pipeline:
    1. Try regex-based rule handling (zero-token path)
    2. If not handled, call Gemini with function-calling + RAG context
    3. Parse the function call result and dispatch to DB helpers
    """
    text = user_text.strip()
    if not text:
        return ChatResponse(type="fallback", message="Please enter a message.")

    # ── Step 1: Regex rule engine (zero-token path) ──
    result = _try_regex_status_update(text, role)
    if result:
        return result

    result = _try_regex_quality_log(text, role)
    if result:
        return result

    result = _try_regex_query(text, role, user_id)
    if result:
        return result

    # ── Step 2: RAG context retrieval ──
    rag_context = ""
    try:
        products = search_products(text, k=3)
        if products:
            snippets = [p["snippet"] for p in products]
            rag_context = "Relevant products from catalog:\n" + "\n".join(f"- {s}" for s in snippets)
    except FileNotFoundError:
        pass  # Index not built yet, skip RAG

    # ── Step 3: Call Gemini with function-calling (model cascade) ──
    try:
        # Build the user prompt with RAG context if available
        prompt_parts = []
        if rag_context:
            prompt_parts.append(rag_context)
        prompt_parts.append(f"User (role={role}): {text}")
        full_prompt = "\n\n".join(prompt_parts)

        # Track token usage
        in_tokens = estimate_tokens(SYSTEM_PROMPT) + estimate_tokens(full_prompt)

        # Use model cascade for resilience against rate limits
        response, model_used = _call_gemini_with_cascade(full_prompt)

        # Extract token usage from response metadata
        out_tokens = 0
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            in_tokens = getattr(response.usage_metadata, "prompt_token_count", in_tokens)
            out_tokens = getattr(response.usage_metadata, "candidates_token_count", 0)

        # Log usage to database
        log_usage(in_tokens, out_tokens)
        usage = UsageInfo(input_tokens=in_tokens, output_tokens=out_tokens,
                          total_tokens=in_tokens + out_tokens, llm_used=True)

        # Check if Gemini returned a function call
        candidate = response.candidates[0] if response.candidates else None
        if candidate and candidate.content and candidate.content.parts:
            function_results = []
            
            for part in candidate.content.parts:
                if hasattr(part, "function_call") and part.function_call:
                    fn_call = part.function_call
                    fn_name = fn_call.name
                    fn_args = dict(fn_call.args) if fn_call.args else {}
                    res = _dispatch_function(fn_name, fn_args, role, user_id)
                    function_results.append(res)
                    
            if function_results:
                if len(function_results) == 1:
                    result = function_results[0]
                    result.usage = usage
                    return result
                else:
                    # Combine multiple results
                    combined_msg = "\n\n".join(r.message for r in function_results)
                    combined_payloads = [r.payload for r in function_results if r.payload]
                    return ChatResponse(
                        type="function",
                        name="multiple",
                        payload={"results": combined_payloads},
                        message=combined_msg,
                        usage=usage
                    )

            # No function call — return text response
            text_response = ""
            for part in candidate.content.parts:
                if hasattr(part, "text") and part.text:
                    text_response += part.text
            if text_response:
                return ChatResponse(type="fallback", message=text_response, usage=usage)

        return ChatResponse(type="fallback", message="🤔 I couldn't understand that. Please rephrase.", usage=usage)

    except Exception as e:
        err_str = str(e)
        # Provide a friendlier error for quota exhaustion
        if "429" in err_str:
            return ChatResponse(
                type="fallback",
                message=(
                    "⚠️ All Gemini models are currently rate-limited. "
                    "Your free-tier daily quota has been exhausted.\n\n"
                    "**What still works without AI:**\n"
                    "• \"Show me all orders\" — query orders\n"
                    "• \"Accept order #1\" — update status\n"
                    "• \"Quality update on order #1 — passed\" — log quality\n\n"
                    "The quota resets daily, or you can use a new API key."
                ),
            )
        return ChatResponse(type="fallback", message=f"⚠️ AI service error: {str(e)}")
