"""Checkout service for managing the lifecycle of checkout sessions."""

import datetime
import hashlib
import json
import logging
import uuid

import httpx

import db
from enums import CheckoutStatus
from exceptions import (
  CheckoutNotModifiableError,
  IdempotencyConflictError,
  InvalidRequestError,
  OutOfStockError,
  PaymentFailedError,
  ResourceNotFoundError,
)
from models import (
  Allocation,
  Cart,
  AppliedDiscount,
  Checkout,
  CheckoutCompleteRequest,
  CheckoutCreateRequest,
  CheckoutUpdateRequest,
  CheckoutLink,
  DiscountsObject,
  Expectation,
  ExpectationLineItem,
  FulfillmentAvailableMethod,
  FulfillmentGroupResponse,
  FulfillmentMethodResponse,
  FulfillmentResponse,
  ItemResponse,
  LineItemResponse,
  Order,
  OrderConfirmation,
  OrderFulfillment,
  OrderLineItem,
  OrderQuantity,
  PaymentResponse,
  PlatformConfig,
  PostalAddress,
  ResponseCheckout,
  ResponseOrder,
  RetailLocation,
  ShippingDestinationResponse,
  TotalResponse,
)
from services.fulfillment_service import FulfillmentService

logger = logging.getLogger(__name__)

SERVER_VERSION = "2026-04-08"


class CheckoutService:
  def __init__(self, fulfillment_service, d1_db, base_url):
    self.fulfillment_service = fulfillment_service
    self.db = d1_db
    self.base_url = base_url.rstrip("/")

  def _build_ucp_metadata(self):
    return ResponseCheckout(
      version=SERVER_VERSION,
      capabilities={"dev.ucp.shopping.checkout": [{"version": SERVER_VERSION}]},
      payment_handlers={
        "dev.shopify.shop_pay": [{"id": "shop_pay", "version": SERVER_VERSION}],
        "com.google.pay": [{"id": "google_pay", "version": SERVER_VERSION}],
      },
    )

  def _compute_hash(self, data):
    if hasattr(data, "model_dump"):
      json_str = json.dumps(data.model_dump(mode="json"), sort_keys=True)
    else:
      json_str = json.dumps(data, sort_keys=True)
    return hashlib.sha256(json_str.encode("utf-8")).hexdigest()

  async def create_checkout(self, checkout_req, idempotency_key, platform_config=None):
    logger.info("Creating checkout session")

    request_hash = self._compute_hash(checkout_req)
    existing_record = await db.get_idempotency_record(self.db, idempotency_key)

    if existing_record:
      if existing_record.request_hash != request_hash:
        raise IdempotencyConflictError("Idempotency key reused with different parameters")
      return Checkout(**existing_record.response_body)

    checkout_id = str(uuid.uuid4())

    # CK5: Server determines currency (from context/geo-IP); default to USD
    currency = "USD"

    # Cart-to-checkout conversion: use cart contents when cart_id is provided
    # Spec: "Business MUST use cart contents (line_items, context, buyer)"
    # and MUST ignore overlapping checkout fields unconditionally.
    cart_context = checkout_req.context
    if checkout_req.cart_id:
      cart_data = await db.get_cart(self.db, checkout_req.cart_id)
      if not cart_data:
        raise ResourceNotFoundError(f"Cart {checkout_req.cart_id} not found")
      cart = Cart(**cart_data)
      if cart.status == "canceled":
        raise InvalidRequestError(f"Cart {checkout_req.cart_id} is canceled")
      # MUST use cart contents unconditionally (ignore overlapping checkout fields)
      line_items = cart.line_items
      checkout_req.buyer = cart.buyer
      currency = cart.currency
      cart_context = cart.context
    else:
      line_items = []
      for li_req in checkout_req.line_items:
        line_items.append(
          LineItemResponse(
            id=str(uuid.uuid4()),
            item=ItemResponse(id=li_req.item.id, title=li_req.item.title or "", price=0),
            quantity=li_req.quantity,
            totals=[],
          )
        )

    # Initialize fulfillment response
    fulfillment_resp = None
    if checkout_req.fulfillment and checkout_req.fulfillment.methods:
      resp_methods = []
      all_li_ids = [li.id for li in line_items]

      for method_req in checkout_req.fulfillment.methods:
        method_id = method_req.id or str(uuid.uuid4())
        method_li_ids = method_req.line_item_ids or all_li_ids
        method_type = method_req.type or "shipping"

        resp_groups = []
        if method_req.groups:
          for group_req in method_req.groups:
            g_id = group_req.id or f"group_{uuid.uuid4()}"
            g_li_ids = group_req.line_item_ids or all_li_ids
            resp_groups.append(
              FulfillmentGroupResponse(
                id=g_id, line_item_ids=g_li_ids,
                selected_option_id=group_req.selected_option_id,
              )
            )

        resp_destinations = []
        if method_type == "pickup":
          # For pickup, use retail locations
          if method_req.destinations:
            for dest_req in method_req.destinations:
              if isinstance(dest_req, RetailLocation) or hasattr(dest_req, "name"):
                resp_destinations.append(RetailLocation(
                  id=dest_req.id or str(uuid.uuid4()),
                  name=dest_req.name,
                  address=getattr(dest_req, "address", None),
                ))
              else:
                resp_destinations.append(RetailLocation(
                  id=getattr(dest_req, "id", None) or str(uuid.uuid4()),
                  name=getattr(dest_req, "name", "Store"),
                ))
          else:
            # Provide default retail locations
            for loc in self.fulfillment_service.get_retail_locations():
              resp_destinations.append(loc)
        elif method_req.destinations:
          for dest_req in method_req.destinations:
            resp_destinations.append(
              ShippingDestinationResponse(
                id=dest_req.id or str(uuid.uuid4()),
                address_country=getattr(dest_req, "address_country", None),
                postal_code=getattr(dest_req, "postal_code", None),
                address_region=getattr(dest_req, "address_region", None),
                address_locality=getattr(dest_req, "address_locality", None),
                street_address=getattr(dest_req, "street_address", None),
              )
            )

        resp_methods.append(
          FulfillmentMethodResponse(
            id=method_id, type=method_type, line_item_ids=method_li_ids,
            groups=resp_groups or None, destinations=resp_destinations or None,
            selected_destination_id=method_req.selected_destination_id,
          )
        )

      # Populate available_methods to signal both shipping and pickup are available
      all_li_ids_list = [li.id for li in line_items]
      available_methods = [
        FulfillmentAvailableMethod(type="shipping", line_item_ids=all_li_ids_list, fulfillable_on="now"),
        FulfillmentAvailableMethod(type="pickup", line_item_ids=all_li_ids_list, fulfillable_on="now",
                                   description="Available for in-store pickup"),
      ]
      fulfillment_resp = FulfillmentResponse(methods=resp_methods, available_methods=available_methods)

    # Build discounts from request
    discounts_obj = None
    if checkout_req.discounts and checkout_req.discounts.codes:
      discounts_obj = DiscountsObject(codes=checkout_req.discounts.codes)

    checkout = Checkout(
      ucp=self._build_ucp_metadata(),
      id=checkout_id,
      status=CheckoutStatus.INCOMPLETE,
      currency=currency,
      line_items=line_items,
      totals=[],
      links=[
        CheckoutLink(type="privacy_policy", url=f"{self.base_url}/policies/privacy", title="Privacy Policy"),
        CheckoutLink(type="terms_of_service", url=f"{self.base_url}/policies/terms", title="Terms of Service"),
        CheckoutLink(type="refund_policy", url=f"{self.base_url}/policies/refunds", title="Refund Policy"),
      ],
      payment=PaymentResponse(
        instruments=checkout_req.payment.instruments if checkout_req.payment else [],
      ),
      buyer=checkout_req.buyer,
      context=cart_context,
      platform=platform_config,
      fulfillment=fulfillment_resp,
      discounts=discounts_obj,
    )

    await self._recalculate_totals(checkout)
    await self._validate_inventory(checkout)

    # CK6: Only advance to ready_for_complete after successful validation
    checkout.status = CheckoutStatus.READY_FOR_COMPLETE

    response_body = checkout.model_dump(mode="json")

    await db.save_checkout(self.db, checkout.id, checkout.status, response_body)
    await db.save_idempotency_record(self.db, idempotency_key, request_hash, 201, response_body)

    return checkout

  async def get_checkout(self, checkout_id):
    await db.log_request(self.db, method="GET", url=f"/checkout-sessions/{checkout_id}", checkout_id=checkout_id)
    return await self._get_and_validate_checkout(checkout_id)

  async def update_checkout(self, checkout_id, checkout_req, idempotency_key, platform_config=None):
    logger.info("Updating checkout session %s", checkout_id)

    request_hash = self._compute_hash(checkout_req)
    existing_record = await db.get_idempotency_record(self.db, idempotency_key)
    if existing_record:
      if existing_record.request_hash != request_hash:
        raise IdempotencyConflictError("Idempotency key reused with different parameters")
      return Checkout(**existing_record.response_body)

    payload_dict = checkout_req.model_dump(mode="json")
    await db.log_request(
      self.db, method="PUT", url=f"/checkout-sessions/{checkout_id}",
      checkout_id=checkout_id, payload=payload_dict,
    )

    existing = await self._get_and_validate_checkout(checkout_id)
    self._ensure_modifiable(existing, "update")

    if checkout_req.line_items:
      line_items = []
      for li_req in checkout_req.line_items:
        line_items.append(
          LineItemResponse(
            id=li_req.id or str(uuid.uuid4()),
            item=ItemResponse(id=li_req.item.id, title=li_req.item.title or "", price=0),
            quantity=li_req.quantity,
            totals=[],
            parent_id=li_req.parent_id,
          )
        )
      existing.line_items = line_items

    if checkout_req.payment:
      existing.payment = PaymentResponse(
        instruments=checkout_req.payment.instruments,
      )

    if checkout_req.buyer:
      existing.buyer = checkout_req.buyer

    if checkout_req.fulfillment and checkout_req.fulfillment.methods:
      customer_addresses = []
      if existing.buyer and existing.buyer.email:
        customer_addresses = await db.get_customer_addresses(self.db, existing.buyer.email)

      resp_methods = []
      for m_req in checkout_req.fulfillment.methods:
        existing_method = None
        if existing.fulfillment and existing.fulfillment.methods:
          existing_method = next(
            (m for m in existing.fulfillment.methods if m.id == m_req.id), None
          )
          if not existing_method and not m_req.id and len(existing.fulfillment.methods) == 1:
            existing_method = existing.fulfillment.methods[0]

        method_id = m_req.id
        if existing_method and not method_id:
          method_id = existing_method.id
        if not method_id:
          method_id = str(uuid.uuid4())

        method_type = m_req.type or "shipping"
        method_li_ids = m_req.line_item_ids or [li.id for li in existing.line_items]

        resp_destinations = []
        if method_type == "pickup":
          if m_req.destinations:
            for dest_req in m_req.destinations:
              if isinstance(dest_req, RetailLocation) or hasattr(dest_req, "name"):
                resp_destinations.append(RetailLocation(
                  id=getattr(dest_req, "id", None) or str(uuid.uuid4()),
                  name=dest_req.name,
                  address=getattr(dest_req, "address", None),
                ))
              else:
                resp_destinations.append(RetailLocation(
                  id=getattr(dest_req, "id", None) or str(uuid.uuid4()),
                  name=getattr(dest_req, "name", "Store"),
                ))
          elif existing_method and existing_method.destinations:
            resp_destinations = existing_method.destinations
          else:
            for loc in self.fulfillment_service.get_retail_locations():
              resp_destinations.append(loc)
        elif method_type == "shipping":
          if m_req.destinations:
            for dest_req in m_req.destinations:
              dest_data = dest_req.model_dump(exclude_none=True)
              if existing.buyer and existing.buyer.email:
                saved_id = await db.save_customer_address(self.db, existing.buyer.email, dest_data)
                dest_data["id"] = saved_id
              resp_destinations.append(ShippingDestinationResponse(**dest_data))
          elif existing_method and existing_method.destinations:
            resp_destinations = existing_method.destinations
          elif customer_addresses:
            for addr in customer_addresses:
              resp_destinations.append(
                ShippingDestinationResponse(
                  id=addr.id, street_address=addr.street_address,
                  address_locality=addr.city, address_region=addr.state,
                  postal_code=addr.postal_code, address_country=addr.country,
                )
              )

        resp_groups = []
        if m_req.groups:
          for g_req in m_req.groups:
            g_id = g_req.id or f"group_{uuid.uuid4()}"
            g_li_ids = g_req.line_item_ids or [li.id for li in existing.line_items]
            resp_groups.append(
              FulfillmentGroupResponse(
                id=g_id, line_item_ids=g_li_ids,
                selected_option_id=g_req.selected_option_id,
              )
            )
        elif existing_method and existing_method.groups:
          resp_groups = existing_method.groups

        resp_methods.append(
          FulfillmentMethodResponse(
            id=method_id, type=method_type, line_item_ids=method_li_ids,
            groups=resp_groups or None, destinations=resp_destinations or None,
            selected_destination_id=m_req.selected_destination_id,
          )
        )

      existing.fulfillment = FulfillmentResponse(methods=resp_methods)

    if checkout_req.discounts:
      existing.discounts = DiscountsObject(codes=checkout_req.discounts.codes)

    if platform_config:
      existing.platform = platform_config

    await self._recalculate_totals(existing)
    await self._validate_inventory(existing)

    response_body = existing.model_dump(mode="json")
    await db.save_checkout(self.db, checkout_id, existing.status, response_body)
    await db.save_idempotency_record(self.db, idempotency_key, request_hash, 200, response_body)

    return existing

  async def complete_checkout(self, checkout_id, complete_req: CheckoutCompleteRequest, idempotency_key):
    logger.info("Completing checkout session %s", checkout_id)

    request_hash = self._compute_hash(complete_req)

    existing_record = await db.get_idempotency_record(self.db, idempotency_key)
    if existing_record:
      if existing_record.request_hash != request_hash:
        raise IdempotencyConflictError("Idempotency key reused with different parameters")
      return Checkout(**existing_record.response_body)

    await db.log_request(
      self.db, method="POST", url=f"/checkout-sessions/{checkout_id}/complete",
      checkout_id=checkout_id, payload=complete_req.model_dump(mode="json"),
    )

    checkout = await self._get_and_validate_checkout(checkout_id)
    self._ensure_modifiable(checkout, "complete")

    await self._process_payment(complete_req.payment)

    # Validate fulfillment
    fulfillment_valid = False
    if checkout.fulfillment and checkout.fulfillment.methods:
      for method in checkout.fulfillment.methods:
        if not method.selected_destination_id:
          continue
        if method.groups:
          for group in method.groups:
            if group.selected_option_id:
              fulfillment_valid = True
              break
        if fulfillment_valid:
          break

    if not fulfillment_valid:
      raise InvalidRequestError("Fulfillment destination and option must be selected before completion.")

    # Reserve inventory
    for line in checkout.line_items:
      product_id = line.item.id
      if await db.get_product(self.db, product_id):
        success = await db.reserve_stock(self.db, product_id, line.quantity)
        if not success:
          raise OutOfStockError(f"Item {product_id} is out of stock", status_code=409)

    checkout.status = CheckoutStatus.COMPLETED
    order_id = str(uuid.uuid4())
    order_permalink_url = f"{self.base_url}/orders/{order_id}"

    checkout.order = OrderConfirmation(id=order_id, permalink_url=order_permalink_url)
    response_body = checkout.model_dump(mode="json")

    # Build order
    expectations = []
    if checkout.fulfillment and checkout.fulfillment.methods:
      for method in checkout.fulfillment.methods:
        selected_dest = None
        dest_description = None
        if method.selected_destination_id and method.destinations:
          for dest in method.destinations:
            if dest.id == method.selected_destination_id:
              if method.type == "pickup" and isinstance(dest, RetailLocation):
                dest_description = f"Pickup at {dest.name}"
                if dest.address:
                  selected_dest = dest.address
              elif hasattr(dest, "name") and not hasattr(dest, "street_address"):
                # RetailLocation loaded from JSON
                dest_description = f"Pickup at {dest.name}"
                if hasattr(dest, "address") and dest.address:
                  selected_dest = PostalAddress(**dest.address) if isinstance(dest.address, dict) else dest.address
              else:
                selected_dest = PostalAddress(
                  street_address=getattr(dest, "street_address", None),
                  address_locality=getattr(dest, "address_locality", None),
                  address_region=getattr(dest, "address_region", None),
                  postal_code=getattr(dest, "postal_code", None),
                  address_country=getattr(dest, "address_country", None),
                )
              break

        if method.groups:
          for group in method.groups:
            if group.selected_option_id and group.options:
              selected_opt = next(
                (o for o in group.options if o.id == group.selected_option_id), None
              )
              if selected_opt:
                exp_line_items = []
                for li in checkout.line_items:
                  if group.line_item_ids and li.id in group.line_item_ids:
                    exp_line_items.append(ExpectationLineItem(id=li.id, quantity=li.quantity))

                exp_description = dest_description or selected_opt.title
                expectations.append(
                  Expectation(
                    id=f"exp_{uuid.uuid4()}",
                    line_items=exp_line_items,
                    method_type=method.type,
                    destination=selected_dest,
                    description=exp_description,
                  )
                )

    order_line_items = []
    for li in checkout.line_items:
      order_line_items.append(
        OrderLineItem(
          id=li.id, item=li.item,
          quantity=OrderQuantity(total=li.quantity, fulfilled=0),
          totals=li.totals, status="processing", parent_id=li.parent_id,
        )
      )

    order = Order(
      ucp=ResponseOrder(
        version=checkout.ucp.version,
        capabilities={"dev.ucp.shopping.order": [{"version": SERVER_VERSION}]},
      ),
      id=order_id, checkout_id=checkout.id,
      permalink_url=order_permalink_url,
      line_items=order_line_items,
      currency=checkout.currency,
      totals=[TotalResponse(**t.model_dump()) for t in checkout.totals],
      fulfillment=OrderFulfillment(expectations=expectations, events=[]),
    )

    await db.save_order(self.db, order.id, order.model_dump(mode="json"))
    await db.save_checkout(self.db, checkout_id, checkout.status, response_body)
    await db.save_idempotency_record(self.db, idempotency_key, request_hash, 200, response_body)

    await self._notify_webhook(checkout, "order_placed")

    return checkout

  async def _notify_webhook(self, checkout, event_type):
    if not checkout.platform or not checkout.platform.webhook_url:
      return

    webhook_url = checkout.platform.webhook_url
    order_data = None
    if checkout.order and checkout.order.id:
      order_data = await db.get_order(self.db, checkout.order.id)

    if not order_data:
      return

    # O1: Send bare order entity as payload (no envelope)
    body_bytes = json.dumps(order_data, separators=(",", ":")).encode("utf-8")

    # O2: Required webhook headers per spec
    import hashlib as _hashlib
    import base64 as _base64
    import time as _time

    content_digest = _base64.b64encode(
      _hashlib.sha256(body_bytes).digest()
    ).decode("ascii")

    webhook_headers = {
      "Content-Type": "application/json",
      "UCP-Agent": f'profile="{self.base_url}/.well-known/ucp"',
      "Webhook-Id": str(uuid.uuid4()),
      "Webhook-Timestamp": str(int(_time.time())),
      "Content-Digest": f"sha-256=:{content_digest}:",
    }

    try:
      async with httpx.AsyncClient() as client:
        await client.post(webhook_url, content=body_bytes, headers=webhook_headers, timeout=5.0)
    except Exception as e:
      logger.error("Failed to notify webhook at %s: %s", webhook_url, e)

  async def ship_order(self, order_id):
    order_data = await db.get_order(self.db, order_id)
    if not order_data:
      raise ResourceNotFoundError("Order not found")

    if "fulfillment" not in order_data:
      order_data["fulfillment"] = {"events": []}
    if "events" not in order_data["fulfillment"] or order_data["fulfillment"]["events"] is None:
      order_data["fulfillment"]["events"] = []

    # Collect all line items for the shipped event
    event_line_items = [
      {"id": li["id"], "quantity": li["quantity"]["total"]}
      for li in order_data.get("line_items", [])
    ]

    order_data["fulfillment"]["events"].append({
      "id": f"evt_{uuid.uuid4()}",
      "type": "shipped",
      "occurred_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
      "line_items": event_line_items,
    })

    await db.save_order(self.db, order_id, order_data)

    checkout_id = order_data.get("checkout_id")
    if checkout_id:
      checkout = await self._get_and_validate_checkout(checkout_id)
      await self._notify_webhook(checkout, "order_shipped")

  async def cancel_checkout(self, checkout_id, idempotency_key):
    logger.info("Canceling checkout session %s", checkout_id)

    request_hash = self._compute_hash({})
    existing_record = await db.get_idempotency_record(self.db, idempotency_key)
    if existing_record:
      if existing_record.request_hash != request_hash:
        raise IdempotencyConflictError("Idempotency key reused with different parameters")
      return Checkout(**existing_record.response_body)

    await db.log_request(
      self.db, method="POST",
      url=f"/checkout-sessions/{checkout_id}/cancel",
      checkout_id=checkout_id,
    )

    checkout = await self._get_and_validate_checkout(checkout_id)
    self._ensure_modifiable(checkout, "cancel")

    checkout.status = CheckoutStatus.CANCELED
    response_body = checkout.model_dump(mode="json")

    await db.save_checkout(self.db, checkout_id, checkout.status, response_body)
    await db.save_idempotency_record(self.db, idempotency_key, request_hash, 200, response_body)

    return checkout

  async def get_order(self, order_id):
    data = await db.get_order(self.db, order_id)
    if not data:
      raise ResourceNotFoundError("Order not found")
    return data

  async def update_order(self, order_id, order):
    await self.get_order(order_id)
    await db.save_order(self.db, order_id, order)
    return order

  async def _get_and_validate_checkout(self, checkout_id):
    data = await db.get_checkout_session(self.db, checkout_id)
    if not data:
      raise ResourceNotFoundError("Checkout session not found")
    return Checkout(**data)

  def _ensure_modifiable(self, checkout, action):
    if checkout.status in [CheckoutStatus.COMPLETED, CheckoutStatus.CANCELED]:
      raise CheckoutNotModifiableError(f"Cannot {action} checkout in state '{checkout.status}'")

  async def _validate_inventory(self, checkout):
    for line in checkout.line_items:
      product_id = line.item.id
      qty_avail = await db.get_inventory(self.db, product_id)
      if qty_avail is None or qty_avail < line.quantity:
        raise OutOfStockError(f"Insufficient stock for item {product_id}")

  async def _recalculate_totals(self, checkout):
    grand_total = 0

    for line in checkout.line_items:
      product_id = line.item.id
      product = await db.get_product(self.db, product_id)
      if not product:
        raise InvalidRequestError(f"Product {product_id} not found")

      line.item.price = product.price
      line.item.title = product.title

      base_amount = product.price * line.quantity
      line.totals = [
        TotalResponse(type="subtotal", display_text="Subtotal", amount=base_amount),
        TotalResponse(type="total", display_text="Total", amount=base_amount),
      ]
      grand_total += base_amount

    checkout.totals = [TotalResponse(type="subtotal", display_text="Subtotal", amount=grand_total)]

    # F2: Capture subtotal before fulfillment costs for percentage discount base
    line_item_subtotal = grand_total

    # Fulfillment
    if checkout.fulfillment and checkout.fulfillment.methods:
      promotions = await db.get_active_promotions(self.db)

      for method in checkout.fulfillment.methods:
        calculated_options = []

        if method.type == "pickup" and method.selected_destination_id:
          # Pickup is free - calculate pickup options
          calculated_options = self.fulfillment_service.calculate_pickup_options()

        elif method.type == "shipping" and method.selected_destination_id:
          selected_dest = None
          if method.destinations:
            for dest in method.destinations:
              if dest.id == method.selected_destination_id:
                selected_dest = dest
                break

          if selected_dest:
            address_obj = PostalAddress(
              street_address=getattr(selected_dest, "street_address", None),
              address_locality=getattr(selected_dest, "address_locality", None),
              address_region=getattr(selected_dest, "address_region", None),
              postal_code=getattr(selected_dest, "postal_code", None),
              address_country=getattr(selected_dest, "address_country", None),
            )

            all_li_ids = [li.id for li in checkout.line_items]
            target_li_ids = method.line_item_ids or all_li_ids
            target_product_ids = []
            for li_uuid in target_li_ids:
              li = next((item for item in checkout.line_items if item.id == li_uuid), None)
              if li:
                target_product_ids.append(li.item.id)

            try:
              calculated_options = await self.fulfillment_service.calculate_options(
                self.db, address_obj, promotions=promotions,
                subtotal=grand_total, line_item_ids=target_product_ids,
              )
            except (ValueError, TypeError) as e:
              logger.error("Failed to calculate options: %s", e)

        if method.selected_destination_id and not method.groups:
          group = FulfillmentGroupResponse(
            id=f"group_{uuid.uuid4()}",
            line_item_ids=method.line_item_ids,
            options=calculated_options,
          )
          method.groups = [group]
        elif method.groups:
          for group in method.groups:
            if calculated_options:
              group.options = calculated_options

            if group.selected_option_id and group.options:
              selected_opt = next(
                (o for o in group.options if o.id == group.selected_option_id), None
              )
              if selected_opt:
                opt_total = next((t.amount for t in selected_opt.totals if t.type == "total"), 0)
                grand_total += opt_total
                display = "In-store pickup" if method.type == "pickup" else "Shipping"
                checkout.totals.append(TotalResponse(type="fulfillment", display_text=display, amount=opt_total))

    # Discounts
    # F3: Reset applied list on every recalculation to prevent re-accumulation
    if not checkout.discounts:
      checkout.discounts = DiscountsObject()
    checkout.discounts.applied = []

    if checkout.discounts.codes:
      discounts = await db.get_discounts_by_codes(self.db, checkout.discounts.codes)
      discount_map = {d.code: d for d in discounts}

      for code in checkout.discounts.codes:
        discount_obj = discount_map.get(code)
        if discount_obj:
          discount_amount = 0
          if discount_obj.type == "percentage":
            # F2: Use line_item_subtotal (excludes fulfillment costs)
            discount_amount = int(line_item_subtotal * (discount_obj.value / 100))
          elif discount_obj.type == "fixed_amount":
            discount_amount = discount_obj.value

          if discount_amount > 0:
            grand_total -= discount_amount
            # CK3/F1: Discount amounts must be negative per spec (exclusiveMaximum: 0)
            checkout.discounts.applied.append(
              AppliedDiscount(
                code=code,
                title=discount_obj.description,
                amount=-discount_amount,
                allocations=[
                  Allocation(path="$.totals[?(@.type=='subtotal')]", amount=-discount_amount)
                ],
              )
            )
            checkout.totals.append(TotalResponse(type="discount", display_text=discount_obj.description or "Discount", amount=-discount_amount))

    checkout.totals.append(TotalResponse(type="total", display_text="Total", amount=grand_total))

  async def _process_payment(self, payment: PaymentResponse):
    instruments = payment.instruments
    if not instruments:
      raise InvalidRequestError("Missing payment instruments")

    selected_instrument = next((i for i in instruments if i.selected), None)
    if not selected_instrument:
      raise InvalidRequestError("No instrument marked as selected")

    handler_id = selected_instrument.handler_id
    credential = selected_instrument.credential
    if not credential:
      raise InvalidRequestError("Missing credentials in instrument")

    token = None
    if isinstance(credential, dict):
      token = credential.get("token")
      if not token and credential.get("number"):
        # Card credential
        logger.info("Processing card payment for card ending in %s", credential["number"][-4:])
        return
    else:
      token = getattr(credential, "token", None)

    if handler_id == "mock_payment_handler":
      if token == "success_token":
        return
      elif token == "fail_token":
        raise PaymentFailedError("Payment Failed: Insufficient Funds (Mock)", code="INSUFFICIENT_FUNDS")
      elif token == "fraud_token":
        raise PaymentFailedError("Payment Failed: Fraud Detected (Mock)", code="FRAUD_DETECTED", status_code=403)
      else:
        raise PaymentFailedError(f"Unknown mock token: {token}", code="UNKNOWN_TOKEN")
    elif handler_id in ("google_pay", "shop_pay"):
      return
    else:
      raise InvalidRequestError(f"Unsupported payment handler: {handler_id}")
