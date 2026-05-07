"""
Factory Mind AI — Pydantic Request / Response Schemas
All API I/O contracts are defined here.
"""

from pydantic import BaseModel, Field
from typing import Optional, Literal, Any


# ─────────────────────────────────────────────
#  AUTH
# ─────────────────────────────────────────────
class LoginRequest(BaseModel):
    """Login with email (or username for admin) and password."""
    email: str = Field(..., description="User email address or username")
    password: str = Field(..., description="User password")

class RegisterRequest(BaseModel):
    """Registration for new users."""
    name: str = Field(..., description="Full name")
    email: str = Field(..., description="Email address")
    password: str = Field(..., description="Password")
    role: str = Field("user", description="User role")


class LoginResponse(BaseModel):
    """JWT token + role returned on successful login."""
    access_token: str
    role: str
    name: str
    user_id: int


# ─────────────────────────────────────────────
#  CHAT
# ─────────────────────────────────────────────
class ChatRequest(BaseModel):
    """Single user utterance sent to the /chat endpoint."""
    message: str = Field(..., min_length=1, description="User's free-text message")


class UsageInfo(BaseModel):
    """Token usage breakdown for a single request."""
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    llm_used: bool = False


class ChatResponse(BaseModel):
    """
    Response from /chat endpoint.
    type='function' means a function was called; type='fallback' is a direct text reply.
    """
    type: Literal["function", "fallback", "rule"] = "fallback"
    name: Optional[str] = Field(None, description="Name of the function that was called")
    payload: Optional[dict[str, Any]] = Field(None, description="Structured result data")
    message: str = Field("", description="Human-readable reply text")
    usage: UsageInfo = Field(default_factory=UsageInfo)


# ─────────────────────────────────────────────
#  ORDERS
# ─────────────────────────────────────────────
class OrderOut(BaseModel):
    """Order data returned to the client (RBAC-filtered)."""
    id: int
    part_name: str
    material: str
    specification: str = ""
    quantity: int
    deadline: str
    notes: str = ""
    status: str
    created_at: str
    cancellable_until: str
    last_quality_note: Optional[str] = None
    last_quality_ts: Optional[str] = None
    user_id: int
    product_id: Optional[int] = None


# ─────────────────────────────────────────────
#  METRICS
# ─────────────────────────────────────────────
class MetricsResponse(BaseModel):
    """Cumulative token usage and cost."""
    total_input_tokens: int
    total_output_tokens: int
    total_tokens: int
    total_calls: int
    estimated_cost_usd: float
