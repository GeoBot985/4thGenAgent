from typing import Any
from pydantic import BaseModel, ConfigDict

class EventIntakeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str
    event_type: str
    payload: dict[str, Any]
    idempotency_key: str | None = None
    dry_run: bool = True
