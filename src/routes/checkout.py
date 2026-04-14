"""Checkout and order routes for the UCP server."""

import logging
import re

import httpx
from fastapi import APIRouter, Body, Header, Path, Request
from pydantic import BaseModel

from models import (
  CheckoutCompleteRequest,
  CheckoutCreateRequest,
  CheckoutUpdateRequest,
  Order,
  PlatformConfig,
)
from services.checkout_service import CheckoutService
from services.fulfillment_service import FulfillmentService

logger = logging.getLogger(__name__)

router = APIRouter()

SERVER_VERSION = "2026-04-08"


# --- Agent profile helpers ---

class UcpConfig(BaseModel):
  webhook_url: str | None = None

class Capability(BaseModel):
  config: UcpConfig | None = None

class UcpProfile(BaseModel):
  capabilities: list[Capability] = []

class AgentProfile(BaseModel):
  ucp: UcpProfile | None = None


async def extract_webhook_url(ucp_agent: str) -> str | None:
  match = re.search(r'profile="([^"]+)"', ucp_agent)
  if not match:
    return None
  profile_uri = match.group(1)
  try:
    async with httpx.AsyncClient() as client:
      response = await client.get(profile_uri)
      if response.status_code != 200:
        return None
      profile = AgentProfile.model_validate(response.json())
      if profile.ucp and profile.ucp.capabilities:
        for cap in profile.ucp.capabilities:
          if cap.config and cap.config.webhook_url:
            return cap.config.webhook_url
  except Exception as e:
    logger.error("Error extracting webhook from %s: %s", profile_uri, e)
  return None


def parse_ucp_agent(ucp_agent: str) -> dict:
  """Parse UCP-Agent header in RFC 8941 Dictionary format.

  Expected format: profile="https://agent.example/.well-known/ucp"
  Returns dict with extracted fields (profile URI, etc).
  """
  result = {}
  # Extract profile URI (RFC 8941 Dictionary: key="value")
  profile_match = re.search(r'profile="([^"]+)"', ucp_agent)
  if profile_match:
    profile_uri = profile_match.group(1)
    if profile_uri.startswith("https://"):
      result["profile"] = profile_uri
  return result


async def validate_ucp_headers(ucp_agent: str):
  parsed = parse_ucp_agent(ucp_agent)
  # D2: Validate profile URI format if present
  if "profile" in parsed:
    profile_uri = parsed["profile"]
    if not profile_uri.startswith("https://"):
      from fastapi import HTTPException
      raise HTTPException(
        status_code=400,
        detail={"code": "INVALID_PROFILE", "message": "UCP-Agent profile must be an HTTPS URL"},
      )


def _get_service(request: Request) -> CheckoutService:
  d1 = request.app.state.db
  return CheckoutService(FulfillmentService(), d1, str(request.base_url))


# --- Checkout routes ---

@router.post("/checkout-sessions", status_code=201)
async def create_checkout(
  request: Request,
  body: CheckoutCreateRequest = Body(...),
  ucp_agent: str = Header(...),
  signature: str = Header(..., alias="Signature"),
  idempotency_key: str = Header(...),
  request_id: str = Header(...),
  signature_input: str | None = Header(None, alias="Signature-Input"),
  content_digest: str | None = Header(None, alias="Content-Digest"),
  authorization: str | None = Header(None, alias="Authorization"),
  x_api_key: str | None = Header(None, alias="X-API-Key"),
):
  await validate_ucp_headers(ucp_agent)
  service = _get_service(request)

  platform_config = None
  webhook_url = await extract_webhook_url(ucp_agent)
  if webhook_url:
    platform_config = PlatformConfig(webhook_url=webhook_url)

  result = await service.create_checkout(body, idempotency_key, platform_config)
  return result.model_dump(mode="json", exclude_none=True)


@router.get("/checkout-sessions/{id}")
async def get_checkout(
  request: Request,
  checkout_id: str = Path(..., alias="id"),
  ucp_agent: str = Header(...),
  signature: str = Header(..., alias="Signature"),
  request_id: str = Header(...),
  signature_input: str | None = Header(None, alias="Signature-Input"),
  content_digest: str | None = Header(None, alias="Content-Digest"),
  authorization: str | None = Header(None, alias="Authorization"),
  x_api_key: str | None = Header(None, alias="X-API-Key"),
):
  await validate_ucp_headers(ucp_agent)
  service = _get_service(request)
  result = await service.get_checkout(checkout_id)
  return result.model_dump(mode="json", exclude_none=True)


@router.put("/checkout-sessions/{id}")
async def update_checkout(
  request: Request,
  body: CheckoutUpdateRequest = Body(...),
  checkout_id: str = Path(..., alias="id"),
  ucp_agent: str = Header(...),
  signature: str = Header(..., alias="Signature"),
  idempotency_key: str = Header(...),
  request_id: str = Header(...),
  signature_input: str | None = Header(None, alias="Signature-Input"),
  content_digest: str | None = Header(None, alias="Content-Digest"),
  authorization: str | None = Header(None, alias="Authorization"),
  x_api_key: str | None = Header(None, alias="X-API-Key"),
):
  await validate_ucp_headers(ucp_agent)
  service = _get_service(request)

  platform_config = None
  webhook_url = await extract_webhook_url(ucp_agent)
  if webhook_url:
    platform_config = PlatformConfig(webhook_url=webhook_url)

  result = await service.update_checkout(checkout_id, body, idempotency_key, platform_config)
  return result.model_dump(mode="json", exclude_none=True)


@router.post("/checkout-sessions/{id}/complete")
async def complete_checkout(
  request: Request,
  checkout_id: str = Path(..., alias="id"),
  body: CheckoutCompleteRequest = Body(...),
  ucp_agent: str = Header(...),
  signature: str = Header(..., alias="Signature"),
  idempotency_key: str = Header(...),
  request_id: str = Header(...),
  signature_input: str | None = Header(None, alias="Signature-Input"),
  content_digest: str | None = Header(None, alias="Content-Digest"),
  authorization: str | None = Header(None, alias="Authorization"),
  x_api_key: str | None = Header(None, alias="X-API-Key"),
):
  await validate_ucp_headers(ucp_agent)
  service = _get_service(request)

  result = await service.complete_checkout(checkout_id, body, idempotency_key)
  return result.model_dump(mode="json", exclude_none=True)


@router.post("/checkout-sessions/{id}/cancel")
async def cancel_checkout(
  request: Request,
  checkout_id: str = Path(..., alias="id"),
  ucp_agent: str = Header(...),
  signature: str = Header(..., alias="Signature"),
  idempotency_key: str = Header(...),
  request_id: str = Header(...),
  signature_input: str | None = Header(None, alias="Signature-Input"),
  content_digest: str | None = Header(None, alias="Content-Digest"),
  authorization: str | None = Header(None, alias="Authorization"),
  x_api_key: str | None = Header(None, alias="X-API-Key"),
):
  await validate_ucp_headers(ucp_agent)
  service = _get_service(request)
  result = await service.cancel_checkout(checkout_id, idempotency_key)
  return result.model_dump(mode="json", exclude_none=True)


# --- Order routes ---

@router.get("/orders/{id}")
async def get_order(
  request: Request,
  order_id: str = Path(..., alias="id"),
  ucp_agent: str = Header(...),
  signature: str = Header(..., alias="Signature"),
  request_id: str = Header(...),
):
  await validate_ucp_headers(ucp_agent)
  service = _get_service(request)
  return await service.get_order(order_id)


@router.put("/orders/{id}")
async def update_order(
  request: Request,
  order_id: str = Path(..., alias="id"),
  order: Order = Body(...),
  ucp_agent: str = Header(...),
  signature: str = Header(..., alias="Signature"),
  request_id: str = Header(...),
):
  await validate_ucp_headers(ucp_agent)
  service = _get_service(request)
  order_data = order.model_dump(mode="json")
  return await service.update_order(order_id, order_data)


@router.post("/testing/simulate-shipping/{id}")
async def ship_order(
  request: Request,
  order_id: str = Path(..., alias="id"),
  simulation_secret: str = Header(..., alias="Simulation-Secret"),
  ucp_agent: str = Header(...),
  signature: str = Header(..., alias="Signature"),
  request_id: str = Header(...),
):
  await validate_ucp_headers(ucp_agent)
  # In a real deployment, validate simulation_secret against config
  service = _get_service(request)
  await service.ship_order(order_id)
  return {"status": "shipped"}


# --- Webhook ---

@router.post("/webhooks/partners/{partner_id}/events/order")
async def order_event_webhook(
  request: Request,
  partner_id: str,
  payload: Order = Body(...),
  signature: str = Header(..., alias="Signature"),
):
  service = _get_service(request)
  payload_dict = payload.model_dump(mode="json")
  await service.update_order(payload.id, payload_dict)
  return {"ucp": {"version": SERVER_VERSION, "status": "success"}}
