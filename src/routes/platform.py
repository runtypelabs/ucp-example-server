"""Session inspector API endpoints — used by the chat widget backend."""

from fastapi import APIRouter, Path, Request
from fastapi.responses import JSONResponse

import db

router = APIRouter()


@router.get("/platform/api/session/{id}")
async def get_session(request: Request, session_id: str = Path(..., alias="id")):
  d1 = request.app.state.db
  result = await db.get_session_by_id(d1, session_id)
  if not result:
    return JSONResponse({"error": "Not found"}, status_code=404)
  return result


@router.get("/platform/api/logs/{id}")
async def get_logs(request: Request, checkout_id: str = Path(..., alias="id")):
  d1 = request.app.state.db
  logs = await db.get_request_logs_for_session(d1, checkout_id)
  return {"logs": logs}
