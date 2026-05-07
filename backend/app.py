"""
Factory Mind AI — FastAPI Application Entrypoint
Stateless API: one POST /chat per user utterance.
"""

import os
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import List

# Ensure backend directory is on the path
sys.path.insert(0, os.path.dirname(__file__))

from db import init_db, get_user_by_email, query_orders as db_query_orders, get_cumulative_usage, verify_password, register_user
from auth import create_access_token, jwt_required
from llm import process_message
from schemas import (
    LoginRequest, LoginResponse, ChatRequest, ChatResponse,
    OrderOut, MetricsResponse, RegisterRequest,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database on startup."""
    init_db()
    yield


app = FastAPI(
    title="Factory Mind AI OMS",
    description="Conversational Order Management — Hybrid AI Architecture",
    version="3.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────
#  HEALTH CHECK
# ─────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "ok", "service": "nova-nexus-api"}


# ─────────────────────────────────────────────
#  AUTH
# ─────────────────────────────────────────────
@app.post("/login", response_model=LoginResponse)
async def login(req: LoginRequest):
    """Login with email/username and password. Returns JWT + role."""
    user = get_user_by_email(req.email)
    if not user:
        raise HTTPException(status_code=401, detail="Unknown email or username.")
    
    if not verify_password(req.password, user["password"]):
        raise HTTPException(status_code=401, detail="Incorrect password.")
        
    token = create_access_token(user["id"], user["role"], user["name"])
    return LoginResponse(
        access_token=token,
        role=user["role"],
        name=user["name"],
        user_id=user["id"],
    )


@app.post("/register", response_model=LoginResponse)
async def register(req: RegisterRequest):
    """Register a new user and return JWT + role."""
    user = register_user(req.email, req.name, req.password, req.role)
    if not user:
        raise HTTPException(status_code=400, detail="Email already registered.")
        
    token = create_access_token(user["id"], user["role"], user["name"])
    return LoginResponse(
        access_token=token,
        role=user["role"],
        name=user["name"],
        user_id=user["id"],
    )


# ─────────────────────────────────────────────
#  CHAT (single stateless endpoint)
# ─────────────────────────────────────────────
@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, current_user: dict = Depends(jwt_required)):
    """
    Process a single user utterance.
    The backend decides (by regex + rule engine) whether the request
    can be handled without LLM; if not, it calls Gemini.
    """
    response = process_message(
        user_text=req.message,
        role=current_user["role"],
        user_id=current_user["id"],
    )
    return response


# ─────────────────────────────────────────────
#  ORDERS
# ─────────────────────────────────────────────
@app.get("/orders", response_model=List[OrderOut])
async def list_orders(
    status: str = None,
    limit: int = 50,
    current_user: dict = Depends(jwt_required),
):
    """Return filtered order list respecting RBAC."""
    orders = db_query_orders(
        status=status,
        limit=limit,
        user_id=current_user["id"],
        role=current_user["role"],
    )
    return orders


# ─────────────────────────────────────────────
#  METRICS
# ─────────────────────────────────────────────
@app.get("/metrics", response_model=MetricsResponse)
async def metrics():
    """Cumulative token usage and estimated cost."""
    return get_cumulative_usage()


# ─────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
