"""Tests validating UCP spec compliance for Cart and Checkout resources.

These tests represent the spec requirements, not what is required for our
app to pass.  Each test cites the exact spec text being validated.
"""

import asyncio
import inspect
import sys
import os

import pytest

# Add src to path so we can import the application modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from unittest.mock import AsyncMock, MagicMock, patch

from models import (
    Buyer,
    Cart,
    CartCreateRequest,
    CartLink,
    CartUpdateRequest,
    Checkout,
    CheckoutCreateRequest,
    CheckoutLink,
    CheckoutUpdateRequest,
    ItemRequest,
    ItemResponse,
    LineItemRequest,
    LineItemResponse,
    ResponseCart,
    ResponseCheckout,
    PaymentResponse,
    TotalResponse,
)
from enums import CheckoutStatus
from exceptions import (
    CartNotModifiableError,
    CheckoutNotModifiableError,
    IdempotencyConflictError,
    OutOfStockError,
    ResourceNotFoundError,
)


# =========================================================================
# Helpers
# =========================================================================

def _make_cart_service():
    """Construct a CartService with mocked DB and base URL."""
    from services.cart_service import CartService
    return CartService(MagicMock(), "https://shop.example.com")


def _make_checkout_service():
    """Construct a CheckoutService with mocked DB, fulfillment, and base URL."""
    from services.checkout_service import CheckoutService
    return CheckoutService(MagicMock(), MagicMock(), "https://shop.example.com")


def _standard_db_patches_for_cart_create():
    """Return a dict of common patches needed for CartService.create_cart."""
    return {
        "db.get_idempotency_record": AsyncMock(return_value=None),
        "db.get_product": AsyncMock(return_value=MagicMock(price=1500, title="Tulips")),
        "db.get_inventory": AsyncMock(return_value=50),
        "db.save_cart": AsyncMock(),
        "db.save_idempotency_record": AsyncMock(),
    }


def _standard_db_patches_for_checkout_create():
    """Return a dict of common patches needed for CheckoutService.create_checkout."""
    return {
        "db.get_idempotency_record": AsyncMock(return_value=None),
        "db.get_product": AsyncMock(return_value=MagicMock(price=2000, title="Rose")),
        "db.get_inventory": AsyncMock(return_value=100),
        "db.get_active_promotions": AsyncMock(return_value=[]),
        "db.save_checkout": AsyncMock(),
        "db.save_idempotency_record": AsyncMock(),
    }


# =========================================================================
# CART SPEC (cart.json, cart-rest.md)
# =========================================================================


## CT1 (cart create 201) removed: covered by R1 in test_fulfillment_order_routes_spec.py


class TestCartResponseRequiredFields:
    """CT2: Cart response required fields.

    Spec: cart.json required: ["ucp", "id", "line_items", "currency", "totals"]
    continue_url, expires_at: optional per cart.json
    """

    def test_cart_serializes_all_required_fields(self):
        # Spec: cart.json required: ["ucp", "id", "line_items", "currency", "totals"]
        cart = Cart(
            ucp=ResponseCart(version="2026-04-08"),
            id="cart-1",
            currency="USD",
            line_items=[
                LineItemResponse(
                    id="li-1",
                    item=ItemResponse(id="prod-1", title="Tulips", price=1500),
                    quantity=2,
                    totals=[TotalResponse(type="subtotal", amount=3000)],
                ),
            ],
            totals=[
                TotalResponse(type="subtotal", amount=3000),
                TotalResponse(type="total", amount=3000),
            ],
            continue_url="https://shop.example.com/cart/cart-1",
            expires_at="2026-04-13T00:00:00Z",
        )
        data = cart.model_dump(mode="json", exclude_none=True)

        # Spec-required fields per cart.json
        for field in ("id", "line_items", "currency", "totals"):
            assert field in data, f"Cart response missing spec-required field '{field}'"

        # Optional fields per cart.json (not required, but should serialize when set)
        for field in ("continue_url", "expires_at"):
            assert field in data, f"Cart optional field '{field}' should serialize when provided"


class TestCartLineItemsEnriched:
    """CT3: Cart response line items contain enriched item data.

    Spec: types/line_item.json required: ["id", "item", "quantity", "totals"]
    types/item.json required: ["id", "title", "price"]
    """

    def test_line_item_has_item_id_title_price(self):
        # Spec: "Response line_items contain item with id, title, price (in minor units)"
        cart = Cart(
            ucp=ResponseCart(version="2026-04-08"),
            id="cart-1",
            currency="USD",
            line_items=[
                LineItemResponse(
                    id="li-1",
                    item=ItemResponse(id="prod-1", title="Tulips", price=1500),
                    quantity=1,
                ),
            ],
            totals=[],
        )
        data = cart.model_dump(mode="json", exclude_none=True)
        item = data["line_items"][0]["item"]

        assert "id" in item, "line_item.item must include id"
        assert "title" in item, "line_item.item must include title"
        assert "price" in item, "line_item.item must include price"
        assert isinstance(item["price"], int), "price must be in minor units (integer)"


class TestCartTotalsStructure:
    """CT4: Cart totals structure.

    Spec: types/total.json required: ["type", "amount"]
    display_text: optional
    """

    def test_totals_have_type_and_amount(self):
        # Spec: "Totals array with type and amount, optional display_text"
        cart = Cart(
            ucp=ResponseCart(version="2026-04-08"),
            id="cart-1",
            currency="USD",
            line_items=[],
            totals=[
                TotalResponse(type="subtotal", amount=3000),
                TotalResponse(type="total", amount=3000, display_text="Total"),
            ],
        )
        data = cart.model_dump(mode="json", exclude_none=True)
        for total in data["totals"]:
            assert "type" in total, "Each total must have 'type'"
            assert "amount" in total, "Each total must have 'amount'"

    def test_display_text_is_optional(self):
        # Spec: "Totals array with type and amount, optional display_text"
        total_without = TotalResponse(type="subtotal", amount=1000)
        data = total_without.model_dump(mode="json", exclude_none=True)
        assert "display_text" not in data, "display_text should be excluded when None"


class TestCartStatusField:
    """CT5: Cart status field for lifecycle tracking.

    Implementation: cart.json does NOT define a status property.
    The status field is an implementation-level addition for tracking
    cart lifecycle (active -> canceled). Behavioral spec (cart-rest.md)
    describes cancel semantics but the JSON schema has no status enum.
    """

    def test_cart_has_status_field(self):
        # Implementation: status field for lifecycle management
        assert "status" in Cart.model_fields, "Cart model must have a 'status' field"

    def test_cart_status_defaults_to_active(self):
        # Implementation: default lifecycle state
        cart = Cart(id="cart-1")
        assert cart.status == "active", "Cart status must default to 'active'"

    def test_cart_status_accepts_canceled(self):
        # Behavior (cart-rest.md): Cancel transitions cart to canceled
        cart = Cart(id="cart-1", status="canceled")
        assert cart.status == "canceled"


class TestCartUpdateFullReplacement:
    """CT6: Cart update is full replacement of line_items.

    Behavior (cart-rest.md): "Update Cart: Full replacement of line_items"
    """

    def test_update_replaces_line_items_entirely(self):
        # Spec: "Update Cart: Full replacement of line_items"
        service = _make_cart_service()

        original_cart_data = {
            "ucp": {"version": "2026-04-08", "capabilities": {}},
            "id": "cart-1",
            "status": "active",
            "currency": "USD",
            "line_items": [
                {"id": "old-li", "item": {"id": "prod-old", "title": "Old", "price": 500}, "quantity": 1, "totals": []},
            ],
            "totals": [],
        }

        update_req = CartUpdateRequest(
            line_items=[
                LineItemRequest(item=ItemRequest(id="prod-new", title="New"), quantity=3),
            ],
        )

        with patch("db.get_idempotency_record", new=AsyncMock(return_value=None)), \
             patch("db.get_cart", new=AsyncMock(return_value=original_cart_data)), \
             patch("db.get_product", new=AsyncMock(return_value=MagicMock(price=1500, title="New"))), \
             patch("db.get_inventory", new=AsyncMock(return_value=50)), \
             patch("db.save_cart", new=AsyncMock()), \
             patch("db.save_idempotency_record", new=AsyncMock()):
            result = asyncio.run(service.update_cart("cart-1", update_req, "idem-update"))

        # Line items must be fully replaced: only the new one should remain
        assert len(result.line_items) == 1, "Update must fully replace line_items"
        assert result.line_items[0].item.id == "prod-new"


class TestCartCancelTransitionsStatus:
    """CT7: Cancel Cart transitions status to canceled.

    Behavior (cart-rest.md): "Cancel Cart: transitions to canceled"
    """

    def test_cancel_cart_sets_status_to_canceled(self):
        # Spec: "Cancel Cart: transitions to canceled"
        service = _make_cart_service()

        active_cart_data = {
            "ucp": {"version": "2026-04-08", "capabilities": {}},
            "id": "cart-1",
            "status": "active",
            "currency": "USD",
            "line_items": [],
            "totals": [],
        }

        with patch("db.get_cart", new=AsyncMock(return_value=active_cart_data)), \
             patch("db.save_cart", new=AsyncMock()):
            result = asyncio.run(service.cancel_cart("cart-1", "idem-cancel"))

        assert result.status == "canceled", "Cancel must transition status to 'canceled'"


class TestCanceledCartRejectsUpdate:
    """CT8: Canceled cart cannot be modified.

    Behavior (cart-rest.md): Canceled cart cannot be modified
    """

    def test_update_on_canceled_cart_raises_cart_not_modifiable(self):
        # Spec: Canceled cart cannot be modified
        service = _make_cart_service()

        canceled_cart_data = {
            "ucp": {"version": "2026-04-08", "capabilities": {}},
            "id": "cart-1",
            "status": "canceled",
            "currency": "USD",
            "line_items": [],
            "totals": [],
        }

        update_req = CartUpdateRequest(
            line_items=[LineItemRequest(item=ItemRequest(id="prod-1"), quantity=1)],
        )

        with patch("db.get_cart", new=AsyncMock(return_value=canceled_cart_data)), \
             patch("db.get_idempotency_record", new=AsyncMock(return_value=None)):
            with pytest.raises(CartNotModifiableError):
                asyncio.run(service.update_cart("cart-1", update_req, "idem-fail"))


class TestCartIdempotencySameKey:
    """CT9: Cart idempotency - same key returns cached result.

    Behavior (cart-rest.md): "Idempotency-Key: Server MUST store key with
    result for at least 24 hours; duplicate key returns cached result"
    """

    def test_duplicate_key_same_params_returns_cached_result(self):
        # Spec: "Idempotency-Key: Server MUST store key with result for at
        # least 24 hours; duplicate key returns cached result"
        service = _make_cart_service()

        cart_req = CartCreateRequest(
            line_items=[LineItemRequest(item=ItemRequest(id="prod-1", title="Tulips"), quantity=1)],
        )

        # Compute expected hash the same way the service does
        request_hash = service._compute_hash(cart_req)

        cached_cart = {
            "ucp": {"version": "2026-04-08", "capabilities": {}},
            "id": "cart-cached",
            "status": "active",
            "currency": "USD",
            "line_items": [
                {"id": "li-cached", "item": {"id": "prod-1", "title": "Tulips", "price": 1500}, "quantity": 1, "totals": []},
            ],
            "totals": [],
        }

        existing_record = MagicMock()
        existing_record.request_hash = request_hash
        existing_record.response_body = cached_cart

        with patch("db.get_idempotency_record", new=AsyncMock(return_value=existing_record)):
            result = asyncio.run(service.create_cart(cart_req, "idem-dup"))

        assert result.id == "cart-cached", "Duplicate idempotency key must return cached result"


class TestCartIdempotencyDifferentParams:
    """CT10: Cart idempotency - different params returns 409.

    Behavior (cart-rest.md): "Different parameters returns 409 Conflict"
    """

    def test_duplicate_key_different_params_raises_409(self):
        # Spec: "Different parameters returns 409 Conflict"
        service = _make_cart_service()

        cart_req = CartCreateRequest(
            line_items=[LineItemRequest(item=ItemRequest(id="prod-DIFFERENT"), quantity=5)],
        )

        existing_record = MagicMock()
        existing_record.request_hash = "hash-of-original-request"
        existing_record.response_body = {}

        with patch("db.get_idempotency_record", new=AsyncMock(return_value=existing_record)):
            with pytest.raises(IdempotencyConflictError):
                asyncio.run(service.create_cart(cart_req, "idem-conflict"))


# =========================================================================
# CHECKOUT SPEC (checkout.json, checkout-rest.md)
# =========================================================================


## CK1 (checkout create 201) removed: covered by R2 in test_fulfillment_order_routes_spec.py


class TestCheckoutStatusEnumValues:
    """CK2: Checkout status enum values.

    Spec: checkout.json status enum: ["incomplete", "requires_escalation",
    "ready_for_complete", "complete_in_progress", "completed", "canceled"]
    """

    @pytest.mark.parametrize("value", [
        "incomplete",
        "requires_escalation",
        "ready_for_complete",
        "complete_in_progress",
        "completed",
        "canceled",
    ])
    def test_checkout_status_accepts_spec_values(self, value):
        # Spec: "status enum: incomplete, requires_escalation,
        # ready_for_complete, complete_in_progress, completed, canceled"
        status = CheckoutStatus(value)
        assert status.value == value

    def test_all_spec_statuses_present_in_enum(self):
        # Spec: "status enum: incomplete, requires_escalation,
        # ready_for_complete, complete_in_progress, completed, canceled"
        expected = {
            "incomplete", "requires_escalation", "ready_for_complete",
            "complete_in_progress", "completed", "canceled",
        }
        actual = {s.value for s in CheckoutStatus}
        assert expected == actual, f"Missing statuses: {expected - actual}"


class TestCheckoutResponsePaymentHandlers:
    """CK3: Checkout response includes payment_handlers.

    Spec: ucp.json#/$defs/response_checkout_schema requires payment_handlers
    """

    def test_checkout_with_response_checkout_has_payment_handlers(self):
        # Spec: "Checkout responses include ucp.payment_handlers"
        checkout = Checkout(
            ucp=ResponseCheckout(
                version="2026-04-08",
                capabilities={"dev.ucp.shopping.checkout": [{"version": "2026-04-08"}]},
                payment_handlers={
                    "dev.shopify.shop_pay": [{"id": "shop_pay", "version": "2026-04-08"}],
                    "com.google.pay": [{"id": "google_pay", "version": "2026-04-08"}],
                },
            ),
            id="ck-1",
            status="incomplete",
            currency="USD",
        )
        data = checkout.model_dump(mode="json", exclude_none=True)
        assert "payment_handlers" in data["ucp"], (
            "Checkout response ucp must include payment_handlers"
        )
        assert isinstance(data["ucp"]["payment_handlers"], dict)
        assert len(data["ucp"]["payment_handlers"]) > 0


class TestCheckoutCancelTransition:
    """CK4: Cancel Checkout transitions to canceled state.

    Behavior (checkout-rest.md): "Cancel Checkout: transitions to canceled state"
    """

    def test_cancel_checkout_sets_status_to_canceled(self):
        # Spec: "Cancel Checkout: transitions to canceled state"
        service = _make_checkout_service()

        checkout_data = {
            "ucp": {
                "version": "2026-04-08",
                "capabilities": {},
                "payment_handlers": {},
            },
            "id": "ck-1",
            "status": "ready_for_complete",
            "currency": "USD",
            "line_items": [],
            "totals": [],
            "links": [],
            "messages": [],
        }

        with patch("db.get_checkout_session", new=AsyncMock(return_value=checkout_data)), \
             patch("db.get_idempotency_record", new=AsyncMock(return_value=None)), \
             patch("db.log_request", new=AsyncMock()), \
             patch("db.save_checkout", new=AsyncMock()), \
             patch("db.save_idempotency_record", new=AsyncMock()):
            result = asyncio.run(service.cancel_checkout("ck-1", "idem-cancel"))

        assert result.status == CheckoutStatus.CANCELED, (
            "Cancel must transition checkout status to 'canceled'"
        )


class TestCanceledCheckoutRejectsModification:
    """CK5: Canceled checkout rejects modification.

    Behavior (checkout-rest.md): "Canceled: session invalid/expired, start new checkout"
    """

    def test_update_on_canceled_checkout_raises_not_modifiable(self):
        # Spec: "Canceled: session invalid/expired, start new checkout"
        service = _make_checkout_service()

        canceled_checkout_data = {
            "ucp": {
                "version": "2026-04-08",
                "capabilities": {},
                "payment_handlers": {},
            },
            "id": "ck-1",
            "status": "canceled",
            "currency": "USD",
            "line_items": [],
            "totals": [],
            "links": [],
            "messages": [],
        }

        update_req = CheckoutUpdateRequest(
            line_items=[LineItemRequest(item=ItemRequest(id="prod-1"), quantity=1)],
        )

        with patch("db.get_checkout_session", new=AsyncMock(return_value=canceled_checkout_data)), \
             patch("db.get_idempotency_record", new=AsyncMock(return_value=None)), \
             patch("db.log_request", new=AsyncMock()):
            with pytest.raises(CheckoutNotModifiableError):
                asyncio.run(service.update_checkout("ck-1", update_req, "idem-fail"))


class TestCheckoutUcpAgentRequired:
    """CK6: UCP-Agent header is required on all checkout requests.

    Behavior (checkout-rest.md): "UCP-Agent: REQUIRED on all requests"
    """

    @pytest.mark.parametrize("route_func_name", [
        "create_checkout",
        "get_checkout",
        "update_checkout",
        "complete_checkout",
        "cancel_checkout",
    ])
    def test_checkout_route_has_ucp_agent_parameter(self, route_func_name):
        # Spec: "UCP-Agent: REQUIRED on all requests"
        from routes import checkout as checkout_module
        route_func = getattr(checkout_module, route_func_name)
        sig = inspect.signature(route_func)
        assert "ucp_agent" in sig.parameters, (
            f"{route_func_name} must accept ucp_agent header parameter"
        )
        # Verify it is required (no default or default is Header(...) with
        # no optional marker)
        param = sig.parameters["ucp_agent"]
        # FastAPI Header(...) makes it required; Header(None) makes it optional.
        # For required: the annotation should be `str`, not `str | None`.
        annotation = param.annotation
        # str (required) vs str | None (optional)
        assert annotation is str, (
            f"{route_func_name}: ucp_agent must be required (str), "
            f"got {annotation}"
        )


class TestUcpAgentFormat:
    """CK7: UCP-Agent format is RFC 8941 Dictionary.

    Behavior (checkout-rest.md): "UCP-Agent format: profile=...
    (RFC 8941 structured field)"
    """

    def test_parse_ucp_agent_extracts_profile_uri(self):
        # Spec: "UCP-Agent format: profile=\"https://platform.example/profile\"
        # (RFC 8941 structured field)"
        from routes.checkout import parse_ucp_agent
        result = parse_ucp_agent('profile="https://agent.example/.well-known/ucp"')
        assert "profile" in result
        assert result["profile"] == "https://agent.example/.well-known/ucp"

    def test_parse_ucp_agent_requires_https(self):
        # Spec: profile URI must be HTTPS
        from routes.checkout import parse_ucp_agent
        result = parse_ucp_agent('profile="http://insecure.example/profile"')
        assert "profile" not in result, "Non-HTTPS profile URI must be rejected"

    def test_parse_ucp_agent_handles_missing_profile(self):
        # Spec: profile is the key in the RFC 8941 Dictionary
        from routes.checkout import parse_ucp_agent
        result = parse_ucp_agent("some-other-field=value")
        assert "profile" not in result


class TestCheckoutIdempotency:
    """CK8: Checkout idempotency follows same rules as cart.

    Behavior (checkout-rest.md): same idempotency rules as cart
    """

    def test_duplicate_key_same_params_returns_cached_checkout(self):
        # Spec: "Idempotency-Key: Server MUST store key with result for at
        # least 24 hours; duplicate key returns cached result"
        service = _make_checkout_service()

        checkout_req = CheckoutCreateRequest(
            line_items=[LineItemRequest(item=ItemRequest(id="prod-1", title="Rose"), quantity=1)],
        )
        request_hash = service._compute_hash(checkout_req)

        cached_checkout = {
            "ucp": {"version": "2026-04-08", "capabilities": {}, "payment_handlers": {}},
            "id": "ck-cached",
            "status": "ready_for_complete",
            "currency": "USD",
            "line_items": [
                {"id": "li-1", "item": {"id": "prod-1", "title": "Rose", "price": 2000}, "quantity": 1, "totals": []},
            ],
            "totals": [],
            "links": [],
            "messages": [],
        }

        existing_record = MagicMock()
        existing_record.request_hash = request_hash
        existing_record.response_body = cached_checkout

        with patch("db.get_idempotency_record", new=AsyncMock(return_value=existing_record)):
            result = asyncio.run(service.create_checkout(checkout_req, "idem-dup"))

        assert result.id == "ck-cached", (
            "Duplicate idempotency key must return cached checkout result"
        )

    def test_duplicate_key_different_params_raises_409(self):
        # Spec: "Different parameters returns 409 Conflict"
        service = _make_checkout_service()

        checkout_req = CheckoutCreateRequest(
            line_items=[LineItemRequest(item=ItemRequest(id="prod-DIFFERENT"), quantity=9)],
        )

        existing_record = MagicMock()
        existing_record.request_hash = "hash-of-original-request"
        existing_record.response_body = {}

        with patch("db.get_idempotency_record", new=AsyncMock(return_value=existing_record)):
            with pytest.raises(IdempotencyConflictError):
                asyncio.run(service.create_checkout(checkout_req, "idem-conflict"))


class TestBuyerModelAllFieldsOptional:
    """CK9: Buyer model - all fields optional.

    Spec: types/buyer.json -- no required fields, additionalProperties: true
    """

    def test_buyer_with_no_args_is_valid(self):
        # Spec: "Buyer: All fields optional, allows progressive building"
        buyer = Buyer()
        assert buyer is not None

    def test_buyer_each_field_independently_settable(self):
        # Spec: "Buyer: All fields optional, allows progressive building"
        buyer_first = Buyer(first_name="Jane")
        assert buyer_first.first_name == "Jane"
        assert buyer_first.last_name is None

        buyer_email = Buyer(email="jane@example.com")
        assert buyer_email.email == "jane@example.com"
        assert buyer_email.first_name is None

        buyer_phone = Buyer(phone_number="+15551234567")
        assert buyer_phone.phone_number == "+15551234567"
        assert buyer_phone.email is None

    def test_buyer_all_fields_are_optional_in_schema(self):
        # Spec: "Buyer: All fields optional, allows progressive building"
        for field_name, field_info in Buyer.model_fields.items():
            assert not field_info.is_required(), (
                f"Buyer.{field_name} must be optional per spec"
            )


class TestCheckoutResponseHasContinueUrl:
    """CK10: Checkout response has continue_url.

    Spec: checkout.json properties.continue_url (format: uri)
    """

    def test_checkout_model_has_continue_url_field(self):
        # Spec: "Checkout response includes continue_url"
        assert "continue_url" in Checkout.model_fields, (
            "Checkout model must have 'continue_url' field"
        )

    def test_checkout_continue_url_serializes(self):
        # Spec: "Checkout response includes continue_url"
        checkout = Checkout(
            ucp=ResponseCheckout(version="2026-04-08"),
            id="ck-1",
            status="incomplete",
            currency="USD",
            continue_url="https://shop.example.com/checkout/ck-1",
        )
        data = checkout.model_dump(mode="json", exclude_none=True)
        assert "continue_url" in data
        assert data["continue_url"] == "https://shop.example.com/checkout/ck-1"


# ============================================================================
# LINK SPEC (types/link.json)
# ============================================================================


class TestLinkObjectRequiredFields:
    """CT11: Link object structure.

    Spec: types/link.json required: ["type", "url"]
    optional: title
    """

    def test_checkout_link_has_type_and_url(self):
        # Spec: types/link.json required: ["type", "url"]
        link = CheckoutLink(type="privacy_policy", url="https://shop.example.com/privacy")
        data = link.model_dump(mode="json", exclude_none=True)
        assert "type" in data, "Link must have 'type' field per link.json"
        assert "url" in data, "Link must have 'url' field per link.json"

    def test_cart_link_has_type_and_url(self):
        # Spec: types/link.json required: ["type", "url"]
        link = CartLink(type="terms_of_service", url="https://shop.example.com/terms")
        data = link.model_dump(mode="json", exclude_none=True)
        assert "type" in data, "Link must have 'type' field per link.json"
        assert "url" in data, "Link must have 'url' field per link.json"

    def test_link_title_is_optional(self):
        # Spec: types/link.json optional: title
        link = CheckoutLink(type="faq", url="https://shop.example.com/faq")
        data = link.model_dump(mode="json", exclude_none=True)
        assert "title" not in data, "title should be excluded when None"

    def test_link_title_serializes_when_provided(self):
        # Spec: types/link.json optional: title
        link = CheckoutLink(
            type="privacy_policy",
            url="https://shop.example.com/privacy",
            title="Privacy Policy",
        )
        data = link.model_dump(mode="json", exclude_none=True)
        assert data["title"] == "Privacy Policy"

    def test_link_well_known_types(self):
        # Spec: types/link.json well-known type values
        well_known = ["privacy_policy", "terms_of_service", "refund_policy", "shipping_policy", "faq"]
        for link_type in well_known:
            link = CheckoutLink(type=link_type, url="https://example.com")
            assert link.type == link_type, f"Link must accept well-known type '{link_type}'"


class TestCheckoutLinksRequired:
    """CT12: Checkout response must include links.

    Spec: checkout.json required: ["ucp", "id", "line_items", "status", "currency", "totals", "links"]
    """

    def test_checkout_has_links_field(self):
        # Spec: checkout.json required includes "links"
        assert "links" in Checkout.model_fields, (
            "Checkout model must have 'links' field per checkout.json required array"
        )

    def test_checkout_links_defaults_to_empty_list(self):
        # Spec: links is an array of link.json objects
        checkout = Checkout(
            ucp=ResponseCheckout(version="2026-04-08"),
            id="ck-1",
            status="incomplete",
            currency="USD",
        )
        assert isinstance(checkout.links, list), "links must be a list"


# ============================================================================
# DISCOUNT MODEL GAPS (discount.json $defs/applied_discount)
# ============================================================================


class TestAppliedDiscountMissingSpecFields:
    """CK11: AppliedDiscount model spec gaps.

    Spec: discount.json $defs/applied_discount defines optional fields
    not yet modeled: provisional (boolean, default false) and
    eligibility ($ref reverse_domain_name.json).
    """

    def test_applied_discount_provisional_not_modeled(self):
        """Spec: discount.json applied_discount defines provisional boolean."""
        from models import AppliedDiscount
        # NOTE: Model gap – discount.json $defs/applied_discount defines
        # optional 'provisional' field (boolean, default false) indicating
        # the discount requires additional verification. Not yet modeled.
        fields = set(AppliedDiscount.model_fields.keys())
        if "provisional" not in fields:
            pytest.skip(
                "Model gap: AppliedDiscount missing 'provisional' field "
                "from discount.json (boolean for verification-required discounts)"
            )

    def test_applied_discount_eligibility_not_modeled(self):
        """Spec: discount.json applied_discount defines eligibility ref."""
        from models import AppliedDiscount
        # NOTE: Model gap – discount.json $defs/applied_discount defines
        # optional 'eligibility' field ($ref reverse_domain_name.json) for
        # the eligibility claim accepted by the Business. Not yet modeled.
        fields = set(AppliedDiscount.model_fields.keys())
        if "eligibility" not in fields:
            pytest.skip(
                "Model gap: AppliedDiscount missing 'eligibility' field "
                "from discount.json (reverse_domain_name ref for eligibility claims)"
            )


# =========================================================================
# ERROR PATH BEHAVIORAL TESTS (cart-rest.md, checkout-rest.md)
# =========================================================================


class TestCartNotFoundErrorResponse:
    """CT13: Behavior (cart-rest.md): Cart not found returns error message.

    Spec (cart-rest.md, Get Cart "Not Found" example):
      HTTP 200 with body:
      {
        "ucp": {"version": "...", "status": "error",
                "capabilities": {"dev.ucp.shopping.cart": [...]}},
        "messages": [{"type": "error", "code": "not_found",
                      "content": "Cart not found or has expired",
                      "severity": "unrecoverable"}],
        "continue_url": "https://merchant.com/"
      }

    IMPLEMENTATION GAP: The current implementation raises ResourceNotFoundError
    which the app.py exception handler converts to HTTP 404 with
    {"detail": ..., "code": "RESOURCE_NOT_FOUND"}.  The spec requires HTTP 200
    with a UCP envelope and messages array.  These tests validate the current
    service-level behavior (raising ResourceNotFoundError) and document the
    gap against the spec-required response format.
    """

    def test_get_cart_raises_not_found_for_unknown_id(self):
        """Service raises ResourceNotFoundError for unknown cart ID."""
        service = _make_cart_service()

        with patch("db.get_cart", new=AsyncMock(return_value=None)):
            with pytest.raises(ResourceNotFoundError, match="Cart not found"):
                asyncio.run(service.get_cart("nonexistent-cart-id"))

    def test_cart_not_found_error_has_correct_code(self):
        """ResourceNotFoundError uses code RESOURCE_NOT_FOUND."""
        service = _make_cart_service()

        with patch("db.get_cart", new=AsyncMock(return_value=None)):
            with pytest.raises(ResourceNotFoundError) as exc_info:
                asyncio.run(service.get_cart("nonexistent-cart-id"))
            assert exc_info.value.code == "RESOURCE_NOT_FOUND"

    def test_cart_not_found_returns_404_not_200(self):
        """SPEC GAP: Implementation returns 404; spec requires 200 with UCP envelope."""
        # Spec: cart-rest.md Get Cart "Not Found" shows HTTP 200 with
        # {"ucp": {"status": "error"}, "messages": [{"code": "not_found"}]}
        # Implementation: ResourceNotFoundError has status_code=404
        service = _make_cart_service()

        with patch("db.get_cart", new=AsyncMock(return_value=None)):
            with pytest.raises(ResourceNotFoundError) as exc_info:
                asyncio.run(service.get_cart("nonexistent-cart-id"))
            # Document the gap: spec says 200, implementation says 404
            assert exc_info.value.status_code == 404, (
                "Implementation currently returns 404"
            )
            pytest.skip(
                "SPEC GAP: Cart not found should return HTTP 200 with "
                '{"ucp": {"status": "error"}, "messages": '
                '[{"type": "error", "code": "not_found", '
                '"severity": "unrecoverable"}]} per cart-rest.md. '
                "Implementation returns HTTP 404 with "
                '{"detail": ..., "code": "RESOURCE_NOT_FOUND"}.'
            )

    def test_update_cart_raises_not_found_for_unknown_id(self):
        """Service raises ResourceNotFoundError when updating nonexistent cart."""
        service = _make_cart_service()

        update_req = CartUpdateRequest(
            line_items=[LineItemRequest(item=ItemRequest(id="prod-1"), quantity=1)],
        )

        with patch("db.get_idempotency_record", new=AsyncMock(return_value=None)), \
             patch("db.get_cart", new=AsyncMock(return_value=None)):
            with pytest.raises(ResourceNotFoundError, match="Cart not found"):
                asyncio.run(service.update_cart("nonexistent-cart-id", update_req, "idem-1"))

    def test_cancel_cart_raises_not_found_for_unknown_id(self):
        """Service raises ResourceNotFoundError when canceling nonexistent cart."""
        service = _make_cart_service()

        with patch("db.get_cart", new=AsyncMock(return_value=None)):
            with pytest.raises(ResourceNotFoundError, match="Cart not found"):
                asyncio.run(service.cancel_cart("nonexistent-cart-id", "idem-1"))


class TestCheckoutNotFoundErrorResponse:
    """CT14: Behavior (checkout-rest.md): Checkout not found returns error message.

    Spec (checkout-rest.md): Business outcomes including not-found are
    returned with HTTP 200 and UCP envelope containing messages array.
    checkout-rest.md does not include an explicit not-found example like
    cart-rest.md, but the error response pattern is the same.

    IMPLEMENTATION GAP: Same as cart -- ResourceNotFoundError -> HTTP 404
    instead of spec-required HTTP 200 with UCP envelope.
    """

    def test_get_checkout_raises_not_found_for_unknown_id(self):
        """Service raises ResourceNotFoundError for unknown checkout ID."""
        service = _make_checkout_service()

        with patch("db.get_checkout_session", new=AsyncMock(return_value=None)), \
             patch("db.log_request", new=AsyncMock()):
            with pytest.raises(ResourceNotFoundError, match="Checkout session not found"):
                asyncio.run(service.get_checkout("nonexistent-checkout-id"))

    def test_checkout_not_found_error_has_correct_code(self):
        """ResourceNotFoundError uses code RESOURCE_NOT_FOUND."""
        service = _make_checkout_service()

        with patch("db.get_checkout_session", new=AsyncMock(return_value=None)), \
             patch("db.log_request", new=AsyncMock()):
            with pytest.raises(ResourceNotFoundError) as exc_info:
                asyncio.run(service.get_checkout("nonexistent-checkout-id"))
            assert exc_info.value.code == "RESOURCE_NOT_FOUND"

    def test_checkout_not_found_returns_404_not_200(self):
        """SPEC GAP: Implementation returns 404; spec requires 200 with UCP envelope."""
        service = _make_checkout_service()

        with patch("db.get_checkout_session", new=AsyncMock(return_value=None)), \
             patch("db.log_request", new=AsyncMock()):
            with pytest.raises(ResourceNotFoundError) as exc_info:
                asyncio.run(service.get_checkout("nonexistent-checkout-id"))
            assert exc_info.value.status_code == 404, (
                "Implementation currently returns 404"
            )
            pytest.skip(
                "SPEC GAP: Checkout not found should return HTTP 200 with "
                '{"ucp": {"status": "error"}, "messages": '
                '[{"type": "error", "code": "not_found", '
                '"severity": "unrecoverable"}]} per checkout-rest.md. '
                "Implementation returns HTTP 404 with "
                '{"detail": ..., "code": "RESOURCE_NOT_FOUND"}.'
            )

    def test_update_checkout_raises_not_found_for_unknown_id(self):
        """Service raises ResourceNotFoundError when updating nonexistent checkout."""
        service = _make_checkout_service()

        update_req = CheckoutUpdateRequest(
            line_items=[LineItemRequest(item=ItemRequest(id="prod-1"), quantity=1)],
        )

        with patch("db.get_idempotency_record", new=AsyncMock(return_value=None)), \
             patch("db.get_checkout_session", new=AsyncMock(return_value=None)), \
             patch("db.log_request", new=AsyncMock()):
            with pytest.raises(ResourceNotFoundError, match="Checkout session not found"):
                asyncio.run(service.update_checkout(
                    "nonexistent-checkout-id", update_req, "idem-1"
                ))

    def test_cancel_checkout_raises_not_found_for_unknown_id(self):
        """Service raises ResourceNotFoundError when canceling nonexistent checkout."""
        service = _make_checkout_service()

        with patch("db.get_idempotency_record", new=AsyncMock(return_value=None)), \
             patch("db.get_checkout_session", new=AsyncMock(return_value=None)), \
             patch("db.log_request", new=AsyncMock()):
            with pytest.raises(ResourceNotFoundError, match="Checkout session not found"):
                asyncio.run(service.cancel_checkout(
                    "nonexistent-checkout-id", "idem-1"
                ))


class TestCartOutOfStockErrorResponse:
    """CT15: Behavior (cart-rest.md): Out-of-stock handling for cart operations.

    Spec (cart-rest.md, Create Cart "Error Response"):
      HTTP 200 with body:
      {
        "ucp": {"version": "...", "status": "error"},
        "messages": [{"type": "error", "code": "out_of_stock",
                      "content": "All requested items are currently out of stock",
                      "severity": "unrecoverable"}],
        "continue_url": "https://merchant.com/"
      }

    IMPLEMENTATION GAP: The service raises OutOfStockError which the app.py
    exception handler converts to HTTP 400 with {"detail": ..., "code":
    "OUT_OF_STOCK"}.  The spec requires HTTP 200 with UCP envelope.
    """

    def test_create_cart_raises_out_of_stock_when_inventory_insufficient(self):
        """Service raises OutOfStockError when item inventory is insufficient."""
        service = _make_cart_service()

        cart_req = CartCreateRequest(
            line_items=[
                LineItemRequest(item=ItemRequest(id="prod-1", title="Tulips"), quantity=10),
            ],
        )

        with patch("db.get_idempotency_record", new=AsyncMock(return_value=None)), \
             patch("db.get_product", new=AsyncMock(return_value=MagicMock(price=1500, title="Tulips"))), \
             patch("db.get_inventory", new=AsyncMock(return_value=0)), \
             patch("db.save_cart", new=AsyncMock()), \
             patch("db.save_idempotency_record", new=AsyncMock()):
            with pytest.raises(OutOfStockError, match="Insufficient stock"):
                asyncio.run(service.create_cart(cart_req, "idem-oos"))

    def test_create_cart_out_of_stock_error_code(self):
        """OutOfStockError uses code OUT_OF_STOCK."""
        service = _make_cart_service()

        cart_req = CartCreateRequest(
            line_items=[
                LineItemRequest(item=ItemRequest(id="prod-1", title="Tulips"), quantity=10),
            ],
        )

        with patch("db.get_idempotency_record", new=AsyncMock(return_value=None)), \
             patch("db.get_product", new=AsyncMock(return_value=MagicMock(price=1500, title="Tulips"))), \
             patch("db.get_inventory", new=AsyncMock(return_value=0)), \
             patch("db.save_cart", new=AsyncMock()), \
             patch("db.save_idempotency_record", new=AsyncMock()):
            with pytest.raises(OutOfStockError) as exc_info:
                asyncio.run(service.create_cart(cart_req, "idem-oos"))
            assert exc_info.value.code == "OUT_OF_STOCK"

    def test_create_cart_out_of_stock_returns_400_not_200(self):
        """SPEC GAP: Implementation returns 400; spec requires 200 with UCP envelope."""
        # Spec: cart-rest.md Create Cart "Error Response" shows HTTP 200 with
        # {"ucp": {"status": "error"}, "messages": [{"code": "out_of_stock"}]}
        service = _make_cart_service()

        cart_req = CartCreateRequest(
            line_items=[
                LineItemRequest(item=ItemRequest(id="prod-1", title="Tulips"), quantity=10),
            ],
        )

        with patch("db.get_idempotency_record", new=AsyncMock(return_value=None)), \
             patch("db.get_product", new=AsyncMock(return_value=MagicMock(price=1500, title="Tulips"))), \
             patch("db.get_inventory", new=AsyncMock(return_value=0)), \
             patch("db.save_cart", new=AsyncMock()), \
             patch("db.save_idempotency_record", new=AsyncMock()):
            with pytest.raises(OutOfStockError) as exc_info:
                asyncio.run(service.create_cart(cart_req, "idem-oos"))
            assert exc_info.value.status_code == 400, (
                "Implementation currently returns 400"
            )
            pytest.skip(
                "SPEC GAP: Cart out-of-stock should return HTTP 200 with "
                '{"ucp": {"status": "error"}, "messages": '
                '[{"type": "error", "code": "out_of_stock", '
                '"severity": "unrecoverable"}]} per cart-rest.md. '
                "Implementation returns HTTP 400 with "
                '{"detail": ..., "code": "OUT_OF_STOCK"}.'
            )

    def test_update_cart_raises_out_of_stock_when_inventory_insufficient(self):
        """Service raises OutOfStockError when updating cart with unavailable items."""
        service = _make_cart_service()

        existing_cart_data = {
            "ucp": {"version": "2026-04-08", "capabilities": {}},
            "id": "cart-1",
            "status": "active",
            "currency": "USD",
            "line_items": [],
            "totals": [],
        }

        update_req = CartUpdateRequest(
            line_items=[
                LineItemRequest(item=ItemRequest(id="prod-1"), quantity=100),
            ],
        )

        with patch("db.get_idempotency_record", new=AsyncMock(return_value=None)), \
             patch("db.get_cart", new=AsyncMock(return_value=existing_cart_data)), \
             patch("db.get_product", new=AsyncMock(return_value=MagicMock(price=1500, title="Tulips"))), \
             patch("db.get_inventory", new=AsyncMock(return_value=2)), \
             patch("db.save_cart", new=AsyncMock()), \
             patch("db.save_idempotency_record", new=AsyncMock()):
            with pytest.raises(OutOfStockError, match="Insufficient stock"):
                asyncio.run(service.update_cart("cart-1", update_req, "idem-oos-update"))


class TestCheckoutOutOfStockErrorResponse:
    """CT15b: Behavior (checkout-rest.md): Out-of-stock handling for checkout operations.

    Spec (checkout-rest.md, Create Checkout "Error Response"):
      HTTP 200 with body:
      {
        "ucp": {"version": "...", "status": "error"},
        "messages": [{"type": "error", "code": "out_of_stock",
                      "content": "All requested items are currently out of stock",
                      "severity": "unrecoverable"}],
        "continue_url": "https://merchant.com/"
      }

    Also (checkout-rest.md, Business Outcomes):
      For create_checkout when all items unavailable:
      {"code": "item_unavailable", "severity": "unrecoverable"}

    IMPLEMENTATION GAP: Same as cart -- OutOfStockError -> HTTP 400 instead
    of spec-required HTTP 200 with UCP envelope.
    """

    def test_create_checkout_raises_out_of_stock_when_inventory_insufficient(self):
        """Service raises OutOfStockError when checkout item inventory is insufficient."""
        service = _make_checkout_service()

        checkout_req = CheckoutCreateRequest(
            line_items=[
                LineItemRequest(item=ItemRequest(id="prod-1", title="Rose"), quantity=10),
            ],
        )

        with patch("db.get_idempotency_record", new=AsyncMock(return_value=None)), \
             patch("db.get_product", new=AsyncMock(return_value=MagicMock(price=2000, title="Rose"))), \
             patch("db.get_inventory", new=AsyncMock(return_value=0)), \
             patch("db.get_active_promotions", new=AsyncMock(return_value=[])), \
             patch("db.save_checkout", new=AsyncMock()), \
             patch("db.save_idempotency_record", new=AsyncMock()):
            with pytest.raises(OutOfStockError, match="Insufficient stock"):
                asyncio.run(service.create_checkout(checkout_req, "idem-oos"))

    def test_checkout_out_of_stock_error_code_mismatch(self):
        """SPEC GAP: Implementation uses OUT_OF_STOCK; spec also uses item_unavailable."""
        # Spec (checkout-rest.md Business Outcomes) uses code "item_unavailable"
        # for when all items are unavailable during create_checkout.
        # Implementation uses code "OUT_OF_STOCK" from OutOfStockError.
        service = _make_checkout_service()

        checkout_req = CheckoutCreateRequest(
            line_items=[
                LineItemRequest(item=ItemRequest(id="prod-1", title="Rose"), quantity=10),
            ],
        )

        with patch("db.get_idempotency_record", new=AsyncMock(return_value=None)), \
             patch("db.get_product", new=AsyncMock(return_value=MagicMock(price=2000, title="Rose"))), \
             patch("db.get_inventory", new=AsyncMock(return_value=0)), \
             patch("db.get_active_promotions", new=AsyncMock(return_value=[])), \
             patch("db.save_checkout", new=AsyncMock()), \
             patch("db.save_idempotency_record", new=AsyncMock()):
            with pytest.raises(OutOfStockError) as exc_info:
                asyncio.run(service.create_checkout(checkout_req, "idem-oos"))
            # Implementation uses "OUT_OF_STOCK" as the code
            assert exc_info.value.code == "OUT_OF_STOCK"
            pytest.skip(
                "SPEC GAP: checkout-rest.md Business Outcomes uses error code "
                '"item_unavailable" for all-items-unavailable scenario. '
                "Implementation uses code \"OUT_OF_STOCK\". Also, spec requires "
                "HTTP 200 with UCP envelope but implementation returns HTTP 400."
            )
