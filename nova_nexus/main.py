"""
Factory Mind AI — Conversational Order Management System
FastAPI Backend  |  DSATM Hackathon 2025

Routes:
  GET  /              → user chat page
  GET  /admin         → admin dashboard + chat
  GET  /orders        → all orders (admin only)
  POST /chat/user     → user: CREATE + QUERY only
  POST /chat/admin    → admin: UPDATE_STATUS + LOG_QUALITY + QUERY
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List
import os

from models import Order, QualityLog, AIResponse
from ai_engine import extract_intent

# ─────────────────────────────────────────────
#  APP SETUP
# ─────────────────────────────────────────────
app = FastAPI(
    title="Factory Mind AI OMS",
    description="Conversational Order Management — DSATM Hackathon 2025",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")


# ─────────────────────────────────────────────
#  IN-MEMORY DATABASE  (shared between roles)
# ─────────────────────────────────────────────
orders_db: List[Order] = []
order_counter: int = 0


def next_id() -> int:
    global order_counter
    order_counter += 1
    return order_counter


def get_order(order_id: int) -> Order:
    for o in orders_db:
        if o.id == order_id:
            return o
    raise HTTPException(status_code=404, detail=f"Order #{order_id} not found.")


# ─────────────────────────────────────────────
#  SCHEMAS
# ─────────────────────────────────────────────
class ChatRequest(BaseModel):
    message: str


class UserChatResponse(BaseModel):
    reply: str                  # user gets only their own reply, no order list


class AdminChatResponse(BaseModel):
    reply: str
    orders: List[Order]         # admin gets full live order list


# ─────────────────────────────────────────────
#  PAGES
# ─────────────────────────────────────────────
@app.get("/", include_in_schema=False)
async def landing_page():
    return FileResponse("static/index.html")


@app.get("/user", include_in_schema=False)
async def user_page():
    return FileResponse("static/user.html")


@app.get("/admin", include_in_schema=False)
async def admin_page():
    return FileResponse("static/admin.html")


# ─────────────────────────────────────────────
#  DATA ENDPOINTS
# ─────────────────────────────────────────────
@app.get("/orders", response_model=List[Order])
async def list_orders():
    """Admin dashboard polls this to refresh the table."""
    return orders_db


# ─────────────────────────────────────────────
#  SHARED INTENT PROCESSOR
# ─────────────────────────────────────────────
def _build_reply(ai: AIResponse, role: str) -> str:
    """
    Execute the AI intent and return a reply string.
    role = "user"  → only CREATE / BULK_CREATE / QUERY allowed
    role = "admin" → only UPDATE_STATUS / LOG_QUALITY / QUERY allowed
    """

    # ── CREATE (user only) ────────────────────────────────────
    if ai.action == "CREATE" and ai.create:
        if role != "user":
            return "⚠️ Only users can place orders."
        c = ai.create
        o = Order(id=next_id(), part_name=c.part_name,
                  material=c.material, quantity=c.quantity, deadline=c.deadline)
        orders_db.append(o)
        return (
            f"✅ Order #{o.id} placed successfully!\n"
            f"  • Part: **{o.part_name}**\n"
            f"  • Material: {o.material}\n"
            f"  • Quantity: {o.quantity} units\n"
            f"  • Deadline: {o.deadline}\n"
            f"  • Status: **{o.status}**\n\n"
            f"The admin team will review your order shortly."
        )

    # ── BULK CREATE (user only) ───────────────────────────────
    if ai.action == "BULK_CREATE" and ai.bulk_create:
        if role != "user":
            return "⚠️ Only users can place orders."
        created = []
        for c in ai.bulk_create.orders:
            o = Order(id=next_id(), part_name=c.part_name,
                      material=c.material, quantity=c.quantity, deadline=c.deadline)
            orders_db.append(o)
            created.append(o)
        lines = [f"✅ **{len(created)} orders** placed from your bulk request!\n"]
        for o in created:
            lines.append(
                f"  • Order #{o.id} — **{o.part_name}** | {o.material} | "
                f"Qty: {o.quantity} | Deadline: {o.deadline}"
            )
        lines.append("\nThe admin team will review your orders shortly.")
        return "\n".join(lines)

    # ── UPDATE STATUS (admin only) ────────────────────────────
    if ai.action == "UPDATE_STATUS" and ai.update_status:
        if role != "admin":
            return "⚠️ Status updates can only be done by the admin."
        u = ai.update_status
        order = get_order(u.order_id)
        progression = {"Received": 0, "In Review": 1, "Accepted": 2}
        if progression[u.new_status] <= progression[order.status]:
            return (
                f"⚠️ Order #{order.id} is already at **{order.status}**. "
                f"Cannot move backwards to '{u.new_status}'."
            )
        old = order.status
        order.status = u.new_status
        return (
            f"🔄 Order #{order.id} — **{order.part_name}**\n"
            f"  Status updated: **{old}** → **{order.status}**"
        )

    # ── LOG QUALITY (admin only) ──────────────────────────────
    if ai.action == "LOG_QUALITY" and ai.log_quality:
        if role != "admin":
            return "⚠️ Quality notes can only be logged by the admin."
        lq = ai.log_quality
        order = get_order(lq.order_id)
        log = QualityLog(note=lq.note)
        order.quality_logs.append(log)
        return (
            f"📋 Quality note logged for Order #{order.id} — **{order.part_name}**\n"
            f"  Note: \"{lq.note}\"\n"
            f"  Timestamp: {log.timestamp}"
        )

    # ── QUERY (both roles) ────────────────────────────────────
    if ai.action == "QUERY" and ai.query:
        q = ai.query

        if q.order_id is not None:
            try:
                o = get_order(q.order_id)
                logs_text = ""
                if o.quality_logs:
                    logs_text = "\n  Quality Notes:\n" + "\n".join(
                        f"    [{lg.timestamp}] {lg.note}" for lg in o.quality_logs
                    )
                return (
                    f"🔍 Order #{o.id} — **{o.part_name}**\n"
                    f"  Material: {o.material} | Qty: {o.quantity} | Deadline: {o.deadline}\n"
                    f"  Status: **{o.status}**"
                    f"{logs_text}"
                )
            except HTTPException as e:
                return f"❌ {e.detail}"

        # List / filter
        source = orders_db
        filtered = [o for o in source if o.status == q.filter_status] if q.filter_status else source
        if not filtered:
            label = f"with status '{q.filter_status}'" if q.filter_status else ""
            return f"📭 No orders found {label}."
        label = f"**{q.filter_status}**" if q.filter_status else "all"
        lines = [f"📦 Showing {label} orders ({len(filtered)} total):\n"]
        for o in filtered:
            lines.append(
                f"  #{o.id} | {o.part_name} | {o.material} | "
                f"Qty: {o.quantity} | Deadline: {o.deadline} | Status: {o.status}"
            )
        return "\n".join(lines)

    # ── UNKNOWN ───────────────────────────────────────────────
    hint = ai.unknown.message if ai.unknown else "I didn't understand that. Please rephrase."
    return f"🤔 {hint}"


# ─────────────────────────────────────────────
#  CHAT ENDPOINTS
# ─────────────────────────────────────────────
@app.post("/chat/user", response_model=UserChatResponse)
async def user_chat(req: ChatRequest):
    """User endpoint — place orders and check status only."""
    msg = req.message.strip()
    if not msg:
        raise HTTPException(status_code=400, detail="Message cannot be empty.")
    try:
        ai = extract_intent(msg)
    except Exception as e:
        return UserChatResponse(reply=f"⚠️ AI service error: {str(e)}")

    # Block admin-only actions on user endpoint
    if ai.action in ("UPDATE_STATUS", "LOG_QUALITY"):
        return UserChatResponse(
            reply="⚠️ You don't have permission to update order status or log quality notes. "
                  "Please contact the admin team."
        )

    reply = _build_reply(ai, role="user")
    return UserChatResponse(reply=reply)


@app.post("/chat/admin", response_model=AdminChatResponse)
async def admin_chat(req: ChatRequest):
    """Admin endpoint — manage orders, update status, log quality."""
    msg = req.message.strip()
    if not msg:
        raise HTTPException(status_code=400, detail="Message cannot be empty.")
    try:
        ai = extract_intent(msg)
    except Exception as e:
        return AdminChatResponse(reply=f"⚠️ AI service error: {str(e)}", orders=orders_db)

    reply = _build_reply(ai, role="admin")
    return AdminChatResponse(reply=reply, orders=orders_db)


# ─────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
