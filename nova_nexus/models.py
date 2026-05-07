"""
Pydantic models for Factory Mind AI Order Management System.
Defines Order schema and AI Intent extraction schemas.
"""

from pydantic import BaseModel, Field
from typing import Optional, Literal, List
from datetime import datetime


# ─────────────────────────────────────────────
#  CORE DOMAIN MODELS
# ─────────────────────────────────────────────

class QualityLog(BaseModel):
    """A single timestamped quality note for an order."""
    note: str
    timestamp: str = Field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


class Order(BaseModel):
    """Represents a manufacturing/procurement order."""
    id: int
    part_name: str
    material: str
    quantity: int
    deadline: str
    status: Literal["Received", "In Review", "Accepted"] = "Received"
    quality_logs: List[QualityLog] = Field(default_factory=list)
    created_at: str = Field(
        default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )


# ─────────────────────────────────────────────
#  AI INTENT MODELS  (Structured Output schemas)
# ─────────────────────────────────────────────

class CreateOrderIntent(BaseModel):
    """Extracted fields for a single order item."""
    intent: Literal["CREATE"]
    part_name: str = Field(description="Name of the part or item to be ordered")
    material: str = Field(description="Material the part is made of; infer from part name if possible, else 'Not specified'")
    quantity: int = Field(description="Number of units required", gt=0)
    deadline: str = Field(description="Delivery or completion deadline as mentioned by user")


class BulkCreateIntent(BaseModel):
    """
    Used when the user mentions multiple items in one message.
    Each item with a DIFFERENT deadline becomes its own entry.
    Items sharing the SAME deadline are grouped into one entry (combined part_name).
    """
    intent: Literal["BULK_CREATE"]
    orders: List[CreateOrderIntent] = Field(
        description="List of individual order items, split by deadline"
    )


class UpdateStatusIntent(BaseModel):
    """Extracted fields when user wants to advance an order's status."""
    intent: Literal["UPDATE_STATUS"]
    order_id: int = Field(description="The numeric ID of the order to update")
    new_status: Literal["In Review", "Accepted"] = Field(
        description="The target status to move the order to"
    )


class LogQualityIntent(BaseModel):
    """Extracted fields when user wants to log a quality note."""
    intent: Literal["LOG_QUALITY"]
    order_id: int = Field(description="The numeric ID of the order to log quality for")
    note: str = Field(description="The quality observation or inspection note verbatim")


class QueryIntent(BaseModel):
    """Extracted fields when user wants to query/list orders."""
    intent: Literal["QUERY"]
    filter_status: Optional[Literal["Received", "In Review", "Accepted"]] = Field(
        default=None,
        description="Filter orders by this status; null means return all orders"
    )
    order_id: Optional[int] = Field(
        default=None,
        description="If user asks about a specific order by ID"
    )


class UnknownIntent(BaseModel):
    """Fallback when the message doesn't match any known intent."""
    intent: Literal["UNKNOWN"]
    message: str = Field(description="A helpful clarification message to show the user")


class AIResponse(BaseModel):
    """
    Top-level structured output from the LLM.
    action discriminates which sub-model is populated.
    """
    action: Literal["CREATE", "BULK_CREATE", "UPDATE_STATUS", "LOG_QUALITY", "QUERY", "UNKNOWN"]

    create: Optional[CreateOrderIntent] = None
    bulk_create: Optional[BulkCreateIntent] = None
    update_status: Optional[UpdateStatusIntent] = None
    log_quality: Optional[LogQualityIntent] = None
    query: Optional[QueryIntent] = None
    unknown: Optional[UnknownIntent] = None
