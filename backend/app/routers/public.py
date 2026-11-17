"""Public (no login) endpoints used by the marketing landing page.

Only the pure, side-effect-free MITRE rule engine is exposed: no database access, no user data.
Input sizes are capped and each client IP is limited to a few requests per minute.
"""
import time
from collections import defaultdict, deque

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from ..schemas import Category
from ..services.mitre import suggest_techniques

router = APIRouter(prefix="/api/public", tags=["Public demo"])

LIMIT, WINDOW = 20, 60.0  # requests per client IP per window (seconds)
_hits: dict[str, deque] = defaultdict(deque)


class SuggestRequest(BaseModel):
    title: str = Field(default="", max_length=200)
    description: str = Field(default="", max_length=2000)
    category: Category = "Other"


def _rate_limit(ip: str) -> None:
    now = time.monotonic()
    q = _hits[ip]
    while q and now - q[0] > WINDOW:
        q.popleft()
    if len(q) >= LIMIT:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many requests. Please slow down.")
    q.append(now)


@router.post("/mitre-suggest", summary="Try the rule-based ATT&CK suggester (no login)")
def mitre_suggest(body: SuggestRequest, request: Request):
    _rate_limit(request.client.host if request.client else "unknown")
    if not (body.title.strip() or body.description.strip()):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Provide a title or description")
    return {"suggestions": suggest_techniques(body.model_dump())}
