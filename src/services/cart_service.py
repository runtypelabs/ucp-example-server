"""Cart service for managing lightweight pre-checkout exploration sessions."""

import hashlib
import json
import logging
import uuid

import db
from exceptions import (
  CartNotModifiableError,
  IdempotencyConflictError,
  InvalidRequestError,
  OutOfStockError,
  ResourceNotFoundError,
)
from models import (
  Cart,
  CartCreateRequest,
  CartUpdateRequest,
  ItemResponse,
  LineItemResponse,
  ResponseCart,
  TotalResponse,
)

logger = logging.getLogger(__name__)

SERVER_VERSION = "2026-04-08"


class CartService:
  def __init__(self, d1_db, base_url):
    self.db = d1_db
    self.base_url = base_url.rstrip("/")

  def _compute_hash(self, data):
    if hasattr(data, "model_dump"):
      json_str = json.dumps(data.model_dump(mode="json"), sort_keys=True)
    else:
      json_str = json.dumps(data, sort_keys=True)
    return hashlib.sha256(json_str.encode("utf-8")).hexdigest()

  def _build_ucp_metadata(self):
    return ResponseCart(
      version=SERVER_VERSION,
      capabilities={"dev.ucp.shopping.cart": [{"version": SERVER_VERSION}]},
    )

  async def create_cart(self, cart_req: CartCreateRequest, idempotency_key: str):
    logger.info("Creating cart session")

    request_hash = self._compute_hash(cart_req)
    existing_record = await db.get_idempotency_record(self.db, idempotency_key)

    if existing_record:
      if existing_record.request_hash != request_hash:
        raise IdempotencyConflictError("Idempotency key reused with different parameters")
      return Cart(**existing_record.response_body)

    cart_id = str(uuid.uuid4())

    line_items = []
    for li_req in cart_req.line_items:
      line_items.append(
        LineItemResponse(
          id=str(uuid.uuid4()),
          item=ItemResponse(id=li_req.item.id, title=li_req.item.title or "", price=0),
          quantity=li_req.quantity,
          totals=[],
        )
      )

    cart = Cart(
      ucp=self._build_ucp_metadata(),
      id=cart_id,
      status="active",
      currency="USD",
      line_items=line_items,
      totals=[],
      buyer=cart_req.buyer,
      context=cart_req.context,
    )

    await self._recalculate_totals(cart)
    await self._validate_inventory(cart)

    response_body = cart.model_dump(mode="json")

    await db.save_cart(self.db, cart.id, cart.status, response_body)
    await db.save_idempotency_record(self.db, idempotency_key, request_hash, 201, response_body)

    return cart

  async def get_cart(self, cart_id: str):
    data = await db.get_cart(self.db, cart_id)
    if not data:
      raise ResourceNotFoundError("Cart not found")
    return Cart(**data)

  async def update_cart(self, cart_id: str, cart_req: CartUpdateRequest, idempotency_key: str):
    logger.info("Updating cart session %s", cart_id)

    request_hash = self._compute_hash(cart_req)
    existing_record = await db.get_idempotency_record(self.db, idempotency_key)
    if existing_record:
      if existing_record.request_hash != request_hash:
        raise IdempotencyConflictError("Idempotency key reused with different parameters")
      return Cart(**existing_record.response_body)

    existing = await self.get_cart(cart_id)
    if existing.status == "canceled":
      raise CartNotModifiableError("Cannot update a canceled cart")

    # Full replacement of line items (UCP spec)
    if cart_req.line_items is not None:
      line_items = []
      for li_req in cart_req.line_items:
        line_items.append(
          LineItemResponse(
            id=li_req.id or str(uuid.uuid4()),
            item=ItemResponse(id=li_req.item.id, title=li_req.item.title or "", price=0),
            quantity=li_req.quantity,
            totals=[],
          )
        )
      existing.line_items = line_items

    if cart_req.buyer:
      existing.buyer = cart_req.buyer

    if cart_req.context is not None:
      existing.context = cart_req.context

    existing.ucp = self._build_ucp_metadata()

    await self._recalculate_totals(existing)
    await self._validate_inventory(existing)

    response_body = existing.model_dump(mode="json")

    await db.save_cart(self.db, existing.id, existing.status, response_body)
    await db.save_idempotency_record(self.db, idempotency_key, request_hash, 200, response_body)

    return existing

  async def cancel_cart(self, cart_id: str, idempotency_key: str):
    logger.info("Canceling cart session %s", cart_id)

    existing = await self.get_cart(cart_id)
    if existing.status == "canceled":
      raise CartNotModifiableError("Cart is already canceled")

    existing.status = "canceled"
    existing.ucp = self._build_ucp_metadata()

    response_body = existing.model_dump(mode="json")
    await db.save_cart(self.db, existing.id, existing.status, response_body)

    return existing

  async def _validate_inventory(self, cart: Cart):
    for line in cart.line_items:
      product_id = line.item.id
      qty_avail = await db.get_inventory(self.db, product_id)
      if qty_avail is None or qty_avail < line.quantity:
        raise OutOfStockError(f"Insufficient stock for item {product_id}")

  async def _recalculate_totals(self, cart: Cart):
    """Calculate subtotal and total from product prices. No tax/shipping/discount for carts."""
    grand_total = 0

    for line in cart.line_items:
      product_id = line.item.id
      product = await db.get_product(self.db, product_id)
      if not product:
        raise InvalidRequestError(f"Product {product_id} not found")

      line.item.price = product.price
      line.item.title = product.title

      base_amount = product.price * line.quantity
      line.totals = [
        TotalResponse(type="subtotal", amount=base_amount),
        TotalResponse(type="total", amount=base_amount),
      ]
      grand_total += base_amount

    cart.totals = [
      TotalResponse(type="subtotal", amount=grand_total),
      TotalResponse(type="total", amount=grand_total),
    ]
