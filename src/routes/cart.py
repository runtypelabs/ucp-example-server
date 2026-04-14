"""Cart routes for the UCP server."""

import logging

from fastapi import APIRouter, Body, Header, Path, Request

from models import CartCreateRequest, CartUpdateRequest
from services.cart_service import CartService

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_service(request: Request) -> CartService:
  d1 = request.app.state.db
  return CartService(d1, str(request.base_url))


@router.post("/carts", status_code=201)
async def create_cart(
  request: Request,
  body: CartCreateRequest = Body(...),
  signature: str = Header(..., alias="Signature"),
  idempotency_key: str = Header(...),
  request_id: str = Header(...),
  ucp_agent: str | None = Header(None),
  signature_input: str | None = Header(None, alias="Signature-Input"),
  content_digest: str | None = Header(None, alias="Content-Digest"),
  authorization: str | None = Header(None, alias="Authorization"),
  x_api_key: str | None = Header(None, alias="X-API-Key"),
):
  service = _get_service(request)
  result = await service.create_cart(body, idempotency_key)
  return result.model_dump(mode="json", exclude_none=True)


@router.get("/carts/{id}")
async def get_cart(
  request: Request,
  cart_id: str = Path(..., alias="id"),
  signature: str = Header(..., alias="Signature"),
  request_id: str = Header(...),
  ucp_agent: str | None = Header(None),
  signature_input: str | None = Header(None, alias="Signature-Input"),
  content_digest: str | None = Header(None, alias="Content-Digest"),
  authorization: str | None = Header(None, alias="Authorization"),
  x_api_key: str | None = Header(None, alias="X-API-Key"),
):
  service = _get_service(request)
  result = await service.get_cart(cart_id)
  return result.model_dump(mode="json", exclude_none=True)


@router.put("/carts/{id}")
async def update_cart(
  request: Request,
  body: CartUpdateRequest = Body(...),
  cart_id: str = Path(..., alias="id"),
  signature: str = Header(..., alias="Signature"),
  idempotency_key: str = Header(...),
  request_id: str = Header(...),
  ucp_agent: str | None = Header(None),
  signature_input: str | None = Header(None, alias="Signature-Input"),
  content_digest: str | None = Header(None, alias="Content-Digest"),
  authorization: str | None = Header(None, alias="Authorization"),
  x_api_key: str | None = Header(None, alias="X-API-Key"),
):
  service = _get_service(request)
  result = await service.update_cart(cart_id, body, idempotency_key)
  return result.model_dump(mode="json", exclude_none=True)


@router.post("/carts/{id}/cancel")
async def cancel_cart(
  request: Request,
  cart_id: str = Path(..., alias="id"),
  signature: str = Header(..., alias="Signature"),
  idempotency_key: str = Header(...),
  request_id: str = Header(...),
  ucp_agent: str | None = Header(None),
  signature_input: str | None = Header(None, alias="Signature-Input"),
  content_digest: str | None = Header(None, alias="Content-Digest"),
  authorization: str | None = Header(None, alias="Authorization"),
  x_api_key: str | None = Header(None, alias="X-API-Key"),
):
  service = _get_service(request)
  result = await service.cancel_cart(cart_id, idempotency_key)
  return result.model_dump(mode="json", exclude_none=True)
