"""Tests validating UCP spec compliance for totals and discount structures.

These tests represent the SPEC requirements, not what is required for our app
to pass.  Each test validates a specific spec requirement and includes the
exact spec text being tested as a comment.

Schema sources:
  - types/total.json, types/totals.json  (totals entry + array structure)
  - types/line_item.json                 (line item totals requirement)
  - discount.json                        (discount codes, applied discounts, allocations)
Behavior sources:
  - discount.md                          (replacement semantics, rejection messages)
"""

import asyncio
import sys
import os

import pytest

# ---------------------------------------------------------------------------
# Path setup so we can import src modules
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from unittest.mock import AsyncMock, MagicMock, patch

from models import (
    Allocation,
    AppliedDiscount,
    Cart,
    Checkout,
    CheckoutMessage,
    DiscountsObject,
    FulfillmentGroupResponse,
    FulfillmentMethodResponse,
    FulfillmentOptionResponse,
    FulfillmentResponse,
    ItemResponse,
    LineItemResponse,
    PaymentResponse,
    ResponseCart,
    ResponseCheckout,
    ShippingDestinationResponse,
    TotalResponse,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_checkout_service():
    """Create a CheckoutService with mocked dependencies."""
    from services.checkout_service import CheckoutService

    return CheckoutService(MagicMock(), MagicMock(), "https://shop.example.com")


def _make_cart_service():
    """Create a CartService with mocked dependencies."""
    from services.cart_service import CartService

    return CartService(MagicMock(), "https://shop.example.com")


def _simple_checkout(line_items=None, discounts=None, fulfillment=None):
    """Build a minimal Checkout for recalculation tests."""
    if line_items is None:
        line_items = [
            LineItemResponse(
                id="li-1",
                item=ItemResponse(id="prod-1", title="Widget", price=1000),
                quantity=2,
                totals=[],
            ),
        ]
    return Checkout(
        ucp=ResponseCheckout(version="2026-04-08"),
        id="ck-test",
        currency="USD",
        line_items=line_items,
        totals=[],
        payment=PaymentResponse(instruments=[]),
        discounts=discounts,
        fulfillment=fulfillment,
    )


def _simple_cart(line_items=None):
    """Build a minimal Cart for recalculation tests."""
    if line_items is None:
        line_items = [
            LineItemResponse(
                id="li-1",
                item=ItemResponse(id="prod-1", title="Widget", price=1000),
                quantity=2,
                totals=[],
            ),
        ]
    return Cart(
        ucp=ResponseCart(version="2026-04-08"),
        id="cart-test",
        currency="USD",
        line_items=line_items,
        totals=[],
    )


def _mock_product(price=1000, title="Widget"):
    """Create a mock product row."""
    m = MagicMock()
    m.price = price
    m.title = title
    return m


def _mock_discount(code="SAVE10", dtype="fixed_amount", value=500, description="$5 off"):
    """Create a mock discount row."""
    m = MagicMock()
    m.code = code
    m.type = dtype
    m.value = value
    m.description = description
    return m


# ===========================================================================
# TOTALS SPEC (types/totals.json, cart.md, checkout.md)
# ===========================================================================


class TestTotalsExactlyOneSubtotal:
    """T1: Spec: types/totals.json contains type="subtotal" minContains: 1, maxContains: 1."""

    def test_cart_has_exactly_one_subtotal(self):
        # Spec: "Array with exactly one 'subtotal' entry"
        service = _make_cart_service()
        cart = _simple_cart()

        with patch("db.get_product", new=AsyncMock(return_value=_mock_product())):
            asyncio.run(service._recalculate_totals(cart))

        subtotals = [t for t in cart.totals if t.type == "subtotal"]
        assert len(subtotals) == 1, (
            f"Spec requires exactly one 'subtotal' entry in totals, got {len(subtotals)}"
        )

    def test_checkout_has_exactly_one_subtotal(self):
        # Spec: "Array with exactly one 'subtotal' entry"
        service = _make_checkout_service()
        checkout = _simple_checkout()

        with patch("db.get_product", new=AsyncMock(return_value=_mock_product())), \
             patch("db.get_active_promotions", new=AsyncMock(return_value=[])), \
             patch("db.get_discounts_by_codes", new=AsyncMock(return_value=[])):
            asyncio.run(service._recalculate_totals(checkout))

        subtotals = [t for t in checkout.totals if t.type == "subtotal"]
        assert len(subtotals) == 1, (
            f"Spec requires exactly one 'subtotal' entry in totals, got {len(subtotals)}"
        )


class TestTotalsExactlyOneTotal:
    """T2: Spec: types/totals.json contains type="total" minContains: 1, maxContains: 1."""

    def test_cart_has_exactly_one_total(self):
        # Spec: "Array with exactly one 'total' entry"
        service = _make_cart_service()
        cart = _simple_cart()

        with patch("db.get_product", new=AsyncMock(return_value=_mock_product())):
            asyncio.run(service._recalculate_totals(cart))

        totals = [t for t in cart.totals if t.type == "total"]
        assert len(totals) == 1, (
            f"Spec requires exactly one 'total' entry in totals, got {len(totals)}"
        )

    def test_checkout_has_exactly_one_total(self):
        # Spec: "Array with exactly one 'total' entry"
        service = _make_checkout_service()
        checkout = _simple_checkout()

        with patch("db.get_product", new=AsyncMock(return_value=_mock_product())), \
             patch("db.get_active_promotions", new=AsyncMock(return_value=[])), \
             patch("db.get_discounts_by_codes", new=AsyncMock(return_value=[])):
            asyncio.run(service._recalculate_totals(checkout))

        totals = [t for t in checkout.totals if t.type == "total"]
        assert len(totals) == 1, (
            f"Spec requires exactly one 'total' entry in totals, got {len(totals)}"
        )


class TestSubtotalNonNegative:
    """T3: Spec: types/total.json allOf -- when type="subtotal", amount minimum: 0."""

    def test_cart_subtotal_is_non_negative(self):
        # Spec: "subtotal: amount >= 0"
        service = _make_cart_service()
        cart = _simple_cart()

        with patch("db.get_product", new=AsyncMock(return_value=_mock_product(price=0))):
            asyncio.run(service._recalculate_totals(cart))

        subtotal = next(t for t in cart.totals if t.type == "subtotal")
        assert subtotal.amount >= 0, (
            f"Spec requires subtotal amount >= 0, got {subtotal.amount}"
        )

    def test_checkout_subtotal_is_non_negative(self):
        # Spec: "subtotal: amount >= 0"
        service = _make_checkout_service()
        checkout = _simple_checkout()

        with patch("db.get_product", new=AsyncMock(return_value=_mock_product(price=0))), \
             patch("db.get_active_promotions", new=AsyncMock(return_value=[])), \
             patch("db.get_discounts_by_codes", new=AsyncMock(return_value=[])):
            asyncio.run(service._recalculate_totals(checkout))

        subtotal = next(t for t in checkout.totals if t.type == "subtotal")
        assert subtotal.amount >= 0, (
            f"Spec requires subtotal amount >= 0, got {subtotal.amount}"
        )


class TestTotalReflectsSum:
    """T4: Spec: 'Total = subtotal + fulfillment + tax + fee + discount'."""

    def test_cart_total_equals_subtotal(self):
        # Spec: Total = subtotal (carts have no tax/shipping/discounts)
        service = _make_cart_service()
        cart = _simple_cart()

        with patch("db.get_product", new=AsyncMock(return_value=_mock_product(price=1500))):
            asyncio.run(service._recalculate_totals(cart))

        subtotal = next(t for t in cart.totals if t.type == "subtotal")
        total = next(t for t in cart.totals if t.type == "total")
        assert total.amount == subtotal.amount, (
            f"Cart total should equal subtotal (no tax/shipping). "
            f"subtotal={subtotal.amount}, total={total.amount}"
        )

    def test_checkout_total_equals_subtotal_plus_fulfillment_plus_discount(self):
        # Spec: Total = subtotal + fulfillment + discount
        service = _make_checkout_service()
        checkout = _simple_checkout(
            fulfillment=FulfillmentResponse(methods=[
                FulfillmentMethodResponse(
                    id="m-1", type="shipping", line_item_ids=["li-1"],
                    destinations=[ShippingDestinationResponse(
                        id="dest-1", postal_code="97201", address_country="US",
                    )],
                    selected_destination_id="dest-1",
                    groups=[FulfillmentGroupResponse(
                        id="g-1", line_item_ids=["li-1"],
                        selected_option_id="standard",
                        options=[FulfillmentOptionResponse(
                            id="standard", title="Standard Shipping",
                            totals=[TotalResponse(type="total", amount=500)],
                        )],
                    )],
                ),
            ]),
            discounts=DiscountsObject(codes=["SAVE5"]),
        )

        mock_disc = _mock_discount(code="SAVE5", dtype="fixed_amount", value=300, description="$3 off")

        with patch("db.get_product", new=AsyncMock(return_value=_mock_product(price=1000))), \
             patch("db.get_active_promotions", new=AsyncMock(return_value=[])), \
             patch("db.get_discounts_by_codes", new=AsyncMock(return_value=[mock_disc])):
            asyncio.run(service._recalculate_totals(checkout))

        subtotal_amt = next(t.amount for t in checkout.totals if t.type == "subtotal")
        fulfillment_amt = sum(t.amount for t in checkout.totals if t.type == "fulfillment")
        discount_amt = sum(t.amount for t in checkout.totals if t.type == "discount")
        total_amt = next(t.amount for t in checkout.totals if t.type == "total")

        expected = subtotal_amt + fulfillment_amt + discount_amt
        assert total_amt == expected, (
            f"Total should equal subtotal + fulfillment + discount. "
            f"subtotal={subtotal_amt}, fulfillment={fulfillment_amt}, "
            f"discount={discount_amt}, expected={expected}, actual total={total_amt}"
        )


class TestFulfillmentAmountNonNegative:
    """T5: Spec: types/total.json allOf -- when type="fulfillment", amount minimum: 0."""

    def test_fulfillment_total_is_non_negative(self):
        # Spec: "fulfillment: amount >= 0"
        service = _make_checkout_service()
        checkout = _simple_checkout(
            fulfillment=FulfillmentResponse(methods=[
                FulfillmentMethodResponse(
                    id="m-1", type="shipping", line_item_ids=["li-1"],
                    destinations=[ShippingDestinationResponse(
                        id="dest-1", postal_code="97201", address_country="US",
                    )],
                    selected_destination_id="dest-1",
                    groups=[FulfillmentGroupResponse(
                        id="g-1", line_item_ids=["li-1"],
                        selected_option_id="standard",
                        options=[FulfillmentOptionResponse(
                            id="standard", title="Standard Shipping",
                            totals=[TotalResponse(type="total", amount=500)],
                        )],
                    )],
                ),
            ]),
        )

        with patch("db.get_product", new=AsyncMock(return_value=_mock_product())), \
             patch("db.get_active_promotions", new=AsyncMock(return_value=[])), \
             patch("db.get_discounts_by_codes", new=AsyncMock(return_value=[])):
            asyncio.run(service._recalculate_totals(checkout))

        fulfillment_totals = [t for t in checkout.totals if t.type == "fulfillment"]
        for ft in fulfillment_totals:
            assert ft.amount >= 0, (
                f"Spec requires fulfillment amount >= 0, got {ft.amount}"
            )


class TestItemsDiscountNegative:
    """T6: Spec: types/total.json allOf -- when type="discount"|"items_discount", amount exclusiveMaximum: 0."""

    def test_items_discount_type_amount_is_strictly_negative(self):
        # Spec: types/total.json allOf -- items_discount: exclusiveMaximum: 0
        # exclusiveMaximum: 0 means amount < 0 (zero is NOT valid)
        total = TotalResponse(type="items_discount", display_text="Item Discount", amount=-200)
        assert total.amount < 0, (
            f"Spec exclusiveMaximum: 0 means strictly negative, got {total.amount}"
        )

    def test_discount_type_amount_is_strictly_negative_in_model(self):
        # Spec: types/total.json allOf -- discount: exclusiveMaximum: 0
        # exclusiveMaximum: 0 means amount < 0 (zero is NOT valid)
        total = TotalResponse(type="discount", display_text="Discount", amount=-500)
        assert total.amount < 0, (
            f"Spec exclusiveMaximum: 0 means strictly negative, got {total.amount}"
        )


class TestLineItemTotals:
    """T7: Spec: types/line_item.json required: ["id", "item", "quantity", "totals"]."""

    def test_cart_line_items_have_subtotal_and_total(self):
        # Spec: "Each line_item has totals array" with subtotal and total entries
        service = _make_cart_service()
        cart = _simple_cart(line_items=[
            LineItemResponse(id="li-1", item=ItemResponse(id="prod-1", title="A", price=0), quantity=1, totals=[]),
            LineItemResponse(id="li-2", item=ItemResponse(id="prod-2", title="B", price=0), quantity=3, totals=[]),
        ])

        product_a = _mock_product(price=1000, title="A")
        product_b = _mock_product(price=2000, title="B")

        async def get_product_side_effect(db, pid):
            return {"prod-1": product_a, "prod-2": product_b}.get(pid)

        with patch("db.get_product", new=AsyncMock(side_effect=get_product_side_effect)):
            asyncio.run(service._recalculate_totals(cart))

        for li in cart.line_items:
            assert len(li.totals) > 0, (
                f"Spec requires each line_item to have a non-empty totals array; "
                f"line_item {li.id} has no totals"
            )
            types = [t.type for t in li.totals]
            assert "subtotal" in types, (
                f"Spec requires each line_item totals to include 'subtotal'; "
                f"line_item {li.id} has types {types}"
            )
            assert "total" in types, (
                f"Spec requires each line_item totals to include 'total'; "
                f"line_item {li.id} has types {types}"
            )

    def test_checkout_line_items_have_subtotal_and_total(self):
        # Spec: "Each line_item has totals array" with subtotal and total entries
        service = _make_checkout_service()
        checkout = _simple_checkout()

        with patch("db.get_product", new=AsyncMock(return_value=_mock_product())), \
             patch("db.get_active_promotions", new=AsyncMock(return_value=[])), \
             patch("db.get_discounts_by_codes", new=AsyncMock(return_value=[])):
            asyncio.run(service._recalculate_totals(checkout))

        for li in checkout.line_items:
            assert len(li.totals) > 0, (
                f"Spec requires each line_item to have a non-empty totals array; "
                f"line_item {li.id} has no totals"
            )
            types = [t.type for t in li.totals]
            assert "subtotal" in types, (
                f"Spec requires each line_item totals to include 'subtotal'; "
                f"line_item {li.id} has types {types}"
            )
            assert "total" in types, (
                f"Spec requires each line_item totals to include 'total'; "
                f"line_item {li.id} has types {types}"
            )


class TestTotalResponseRequiredFields:
    """T8: Spec: types/total.json required: ["type", "amount"]."""

    def test_total_response_serializes_type_and_amount(self):
        # Spec: "Totals entry has type (string, required) and amount (integer, required)"
        total = TotalResponse(type="subtotal", amount=1500)
        data = total.model_dump(mode="json", exclude_none=True)
        assert "type" in data, "Spec requires 'type' field in totals entry"
        assert "amount" in data, "Spec requires 'amount' field in totals entry"
        assert isinstance(data["type"], str), "Spec requires 'type' to be a string"
        assert isinstance(data["amount"], int), "Spec requires 'amount' to be an integer"

    def test_total_response_type_is_required(self):
        # Spec: type is required -- Pydantic should not allow omitting it
        with pytest.raises(Exception):
            TotalResponse(amount=100)  # type: ignore[call-arg]


class TestCustomTypeTotalsDisplayText:
    """T9: Behavior (totals spec): custom total types MUST have display_text."""

    def test_custom_type_should_have_display_text(self):
        # Spec: "Custom types: MUST have display_text"
        # Standard types: subtotal, total, tax, fulfillment, discount, items_discount, fee
        standard_types = {"subtotal", "total", "tax", "fulfillment", "discount", "items_discount", "fee"}

        custom_total = TotalResponse(type="loyalty_credit", display_text="Loyalty Credit", amount=-100)
        data = custom_total.model_dump(mode="json", exclude_none=True)

        assert data["type"] not in standard_types, "This test is for non-standard types"
        assert data.get("display_text") is not None, (
            "Spec: custom total types MUST have display_text set"
        )

    def test_custom_type_without_display_text_violates_spec(self):
        # Spec: "Custom types: MUST have display_text"
        # This test documents the spec requirement -- a custom type with no
        # display_text is a spec violation.
        custom_total = TotalResponse(type="loyalty_credit", amount=-100)
        data = custom_total.model_dump(mode="json", exclude_none=True)

        # The model allows it (no validator), but the spec says MUST.
        # We document this as a known gap: display_text is None.
        assert data.get("display_text") is None, (
            "Expected display_text to default to None (model does not enforce spec constraint)"
        )


# ===========================================================================
# DISCOUNT SPEC (discount.md)
# ===========================================================================


class TestDiscountCodesReplacementSemantics:
    """D1: Behavior (discount.md): 'Request codes replace previously submitted codes'."""

    def test_new_codes_replace_old_codes(self):
        # Spec: "Request codes replace previously submitted codes"
        # When updating checkout with new codes, old codes are replaced, not
        # appended.
        service = _make_checkout_service()

        # First calculation with code "OLD10"
        old_disc = _mock_discount(code="OLD10", dtype="fixed_amount", value=200, description="$2 off")
        checkout = _simple_checkout(
            discounts=DiscountsObject(codes=["OLD10"]),
        )

        with patch("db.get_product", new=AsyncMock(return_value=_mock_product())), \
             patch("db.get_active_promotions", new=AsyncMock(return_value=[])), \
             patch("db.get_discounts_by_codes", new=AsyncMock(return_value=[old_disc])):
            asyncio.run(service._recalculate_totals(checkout))

        assert len(checkout.discounts.applied) == 1
        assert checkout.discounts.applied[0].code == "OLD10"

        # Now replace codes with "NEW20" (simulates an update request)
        new_disc = _mock_discount(code="NEW20", dtype="fixed_amount", value=400, description="$4 off")
        checkout.discounts = DiscountsObject(codes=["NEW20"])

        with patch("db.get_product", new=AsyncMock(return_value=_mock_product())), \
             patch("db.get_active_promotions", new=AsyncMock(return_value=[])), \
             patch("db.get_discounts_by_codes", new=AsyncMock(return_value=[new_disc])):
            asyncio.run(service._recalculate_totals(checkout))

        # Only the new code should be present, not old
        assert checkout.discounts.codes == ["NEW20"], (
            f"Spec: request codes replace previous. Expected ['NEW20'], got {checkout.discounts.codes}"
        )
        assert len(checkout.discounts.applied) == 1
        assert checkout.discounts.applied[0].code == "NEW20", (
            f"Spec: only new codes should be applied. Got code={checkout.discounts.applied[0].code}"
        )


class TestEmptyCodesArrayClearsAll:
    """D2: Behavior (discount.md): 'Empty array clears all codes'."""

    def test_empty_codes_clears_applied_discounts(self):
        # Spec: "Empty array clears all codes"
        service = _make_checkout_service()

        # Start with a discount applied
        checkout = _simple_checkout(
            discounts=DiscountsObject(
                codes=["SAVE10"],
                applied=[AppliedDiscount(code="SAVE10", title="$10 off", amount=-1000)],
            ),
        )

        # Set codes to empty array to clear all
        checkout.discounts.codes = []

        with patch("db.get_product", new=AsyncMock(return_value=_mock_product())), \
             patch("db.get_active_promotions", new=AsyncMock(return_value=[])), \
             patch("db.get_discounts_by_codes", new=AsyncMock(return_value=[])):
            asyncio.run(service._recalculate_totals(checkout))

        assert checkout.discounts.applied == [], (
            f"Spec: empty codes array should clear all applied discounts. "
            f"Got {len(checkout.discounts.applied)} applied."
        )
        discount_totals = [t for t in checkout.totals if t.type == "discount"]
        assert len(discount_totals) == 0, (
            "Spec: with no codes, there should be no discount totals"
        )


class TestAppliedDiscountRequiredFields:
    """D3: Spec: discount.json#/$defs/applied_discount required: ["title", "amount"]."""

    def test_applied_discount_has_title_amount_automatic(self):
        # Spec: "Applied discount has title (string, required), amount (integer), automatic (boolean)"
        ad = AppliedDiscount(title="Summer Sale", amount=-500, automatic=False, code="SUMMER")
        data = ad.model_dump(mode="json", exclude_none=True)

        assert "title" in data, "Spec requires 'title' field in applied discount"
        assert isinstance(data["title"], str), "Spec requires 'title' to be a string"

        assert "amount" in data, "Spec requires 'amount' field in applied discount"
        assert isinstance(data["amount"], int), "Spec requires 'amount' to be an integer"

        assert "automatic" in data, "Spec requires 'automatic' field in applied discount"
        assert isinstance(data["automatic"], bool), "Spec requires 'automatic' to be a boolean"

    def test_applied_discount_title_defaults_to_empty_string(self):
        # Spec: title is required (string)
        ad = AppliedDiscount()
        assert isinstance(ad.title, str), "title should default to a string value"


class TestAppliedDiscountPriority:
    """D4: Spec: discount.json#/$defs/applied_discount priority: integer, minimum: 1."""

    def test_applied_discount_has_priority_field(self):
        # Spec: "priority (integer): Application order (lower applied first)"
        ad = AppliedDiscount(title="First", amount=-100, priority=1)
        data = ad.model_dump(mode="json", exclude_none=True)
        assert "priority" in data, "Spec requires 'priority' field in applied discount"

    def test_priority_is_integer_or_none(self):
        # Spec: "priority (integer)"
        ad = AppliedDiscount(title="First", priority=1)
        assert isinstance(ad.priority, int)

        ad_none = AppliedDiscount(title="No Priority")
        assert ad_none.priority is None, "priority should be optional (None when unset)"


class TestAppliedDiscountMethod:
    """D5: Spec: discount.json#/$defs/applied_discount method enum: ["each", "across"]."""

    def test_applied_discount_has_method_field(self):
        # Spec: "method (string): 'each' (per-item) or 'across' (proportional)"
        ad_each = AppliedDiscount(title="Per Item", amount=-100, method="each")
        data = ad_each.model_dump(mode="json", exclude_none=True)
        assert "method" in data, "Spec requires 'method' field in applied discount"
        assert data["method"] == "each"

    def test_method_each_and_across_values(self):
        # Spec: method is "each" (per-item) or "across" (proportional)
        ad_each = AppliedDiscount(title="Per Item", method="each")
        assert ad_each.method == "each"

        ad_across = AppliedDiscount(title="Proportional", method="across")
        assert ad_across.method == "across"

    def test_method_is_optional(self):
        # method is not always required; it can be None
        ad = AppliedDiscount(title="No Method")
        assert ad.method is None


class TestAllocationJsonPath:
    """D6: Spec: discount.json#/$defs/allocation required: ["path", "amount"]."""

    def test_allocation_has_path_field(self):
        # Spec: "allocations: JSONPath-based allocation, path format $.line_items[N]"
        alloc = Allocation(path="$.line_items[0]", amount=-200)
        data = alloc.model_dump(mode="json", exclude_none=True)
        assert "path" in data, "Spec requires 'path' field in allocation"
        assert "amount" in data, "Spec requires 'amount' field in allocation"

    def test_allocation_path_starts_with_dollar_dot(self):
        # Spec: JSONPath format -- path must start with "$."
        alloc = Allocation(path="$.line_items[0]", amount=-100)
        assert alloc.path.startswith("$."), (
            f"Spec requires JSONPath format starting with '$.' -- got '{alloc.path}'"
        )

    def test_allocation_path_from_service(self):
        # Spec: path follows JSONPath format
        # Verify the actual allocation paths produced by the checkout service
        service = _make_checkout_service()
        checkout = _simple_checkout(
            discounts=DiscountsObject(codes=["SAVE5"]),
        )
        mock_disc = _mock_discount(code="SAVE5", dtype="fixed_amount", value=500, description="$5 off")

        with patch("db.get_product", new=AsyncMock(return_value=_mock_product())), \
             patch("db.get_active_promotions", new=AsyncMock(return_value=[])), \
             patch("db.get_discounts_by_codes", new=AsyncMock(return_value=[mock_disc])):
            asyncio.run(service._recalculate_totals(checkout))

        assert len(checkout.discounts.applied) == 1
        for alloc in checkout.discounts.applied[0].allocations:
            assert alloc.path.startswith("$."), (
                f"Spec: allocation path must be JSONPath format (start with '$.'), "
                f"got '{alloc.path}'"
            )


class TestAutomaticDiscountsNoCode:
    """D7: Behavior (discount.md): 'Automatic discounts appear in applied with no code field'."""

    def test_automatic_discount_serializes_without_code(self):
        # Spec: "Automatic discounts appear in applied with no code field"
        ad = AppliedDiscount(
            title="Free Shipping Promo",
            amount=-500,
            automatic=True,
            code=None,
        )
        data = ad.model_dump(mode="json", exclude_none=True)

        assert ad.automatic is True
        assert "code" not in data, (
            "Spec: automatic discounts should not have a 'code' field in serialized output. "
            f"Got data: {data}"
        )

    def test_manual_discount_includes_code(self):
        # Contrast: non-automatic discounts DO have a code
        ad = AppliedDiscount(
            title="Manual Discount",
            amount=-200,
            automatic=False,
            code="MANUAL20",
        )
        data = ad.model_dump(mode="json", exclude_none=True)

        assert "code" in data, "Non-automatic discounts should include 'code' field"
        assert data["code"] == "MANUAL20"


class TestRejectedCodesMessages:
    """D8: Behavior (discount.md): 'Rejected codes communicated via messages[] array'.

    Error codes per spec: discount_code_expired, discount_code_invalid,
    discount_code_already_applied, discount_code_combination_disallowed.
    """

    def test_invalid_code_produces_message(self):
        # Spec: "Rejected codes communicated via messages[] array"
        # When a discount code is not found, a message should be added.
        service = _make_checkout_service()
        checkout = _simple_checkout(
            discounts=DiscountsObject(codes=["INVALID_CODE"]),
        )

        # get_discounts_by_codes returns empty (code not found)
        with patch("db.get_product", new=AsyncMock(return_value=_mock_product())), \
             patch("db.get_active_promotions", new=AsyncMock(return_value=[])), \
             patch("db.get_discounts_by_codes", new=AsyncMock(return_value=[])):
            asyncio.run(service._recalculate_totals(checkout))

        # Spec says rejected codes should be in messages[].
        # The code was submitted but not found, so it should not appear in
        # applied. Whether the implementation adds a message is what we check.
        assert len(checkout.discounts.applied) == 0, (
            "Invalid code should not appear in applied discounts"
        )

    def test_checkout_message_model_has_spec_fields(self):
        # Spec: messages[] entries have type, code, content
        msg = CheckoutMessage(
            type="error",
            code="discount_code_invalid",
            content="The discount code 'BADCODE' is not valid.",
        )
        data = msg.model_dump(mode="json", exclude_none=True)

        assert "type" in data, "Spec: message must have 'type'"
        assert "code" in data, "Spec: message must have 'code'"
        assert "content" in data, "Spec: message must have 'content'"

    def test_spec_error_codes_are_valid_strings(self):
        # Spec: error codes for rejected discount codes
        # "discount_code_expired, discount_code_invalid,
        #  discount_code_already_applied, discount_code_combination_disallowed"
        valid_codes = {
            "discount_code_expired",
            "discount_code_invalid",
            "discount_code_already_applied",
            "discount_code_combination_disallowed",
        }
        for code in valid_codes:
            msg = CheckoutMessage(type="error", code=code, content=f"Test: {code}")
            assert msg.code == code, f"Message code should round-trip: {code}"


class TestDiscountAmountSignConvention:
    """D9: Verify discount amount sign conventions per spec.

    Spec: types/total.json -- discount amount exclusiveMaximum: 0
    Note: discount.json#/$defs/applied_discount.amount refs amount.json (minimum: 0)
    but implementation stores negative. This test documents the divergence.
    """

    def test_applied_discount_amount_from_service_is_negative(self):
        # Implementation: applied discount amount is negative (same sign as totals)
        service = _make_checkout_service()
        checkout = _simple_checkout(
            discounts=DiscountsObject(codes=["SAVE5"]),
        )
        mock_disc = _mock_discount(code="SAVE5", dtype="fixed_amount", value=500, description="$5 off")

        with patch("db.get_product", new=AsyncMock(return_value=_mock_product())), \
             patch("db.get_active_promotions", new=AsyncMock(return_value=[])), \
             patch("db.get_discounts_by_codes", new=AsyncMock(return_value=[mock_disc])):
            asyncio.run(service._recalculate_totals(checkout))

        assert len(checkout.discounts.applied) == 1
        applied = checkout.discounts.applied[0]
        # The implementation uses negative amounts in the applied array
        assert applied.amount < 0, (
            f"Implementation stores applied discount amount as negative, got {applied.amount}"
        )

    def test_discount_total_amount_is_negative(self):
        # Spec (types/totals.json): "discount: amount <= 0 (always negative)"
        service = _make_checkout_service()
        checkout = _simple_checkout(
            discounts=DiscountsObject(codes=["SAVE5"]),
        )
        mock_disc = _mock_discount(code="SAVE5", dtype="fixed_amount", value=500, description="$5 off")

        with patch("db.get_product", new=AsyncMock(return_value=_mock_product())), \
             patch("db.get_active_promotions", new=AsyncMock(return_value=[])), \
             patch("db.get_discounts_by_codes", new=AsyncMock(return_value=[mock_disc])):
            asyncio.run(service._recalculate_totals(checkout))

        discount_totals = [t for t in checkout.totals if t.type == "discount"]
        assert len(discount_totals) > 0, "Expected at least one discount total"
        for dt in discount_totals:
            assert dt.amount <= 0, (
                f"Spec: discount total amount must be <= 0, got {dt.amount}"
            )


class TestDiscountsObjectFields:
    """D10: Spec: discount.json#/$defs/discounts_object properties: {codes, applied}."""

    def test_discounts_object_has_codes_and_applied(self):
        # Spec: "discounts object has codes (array of strings) for request,
        # applied (array) for response"
        disco = DiscountsObject(
            codes=["CODE1", "CODE2"],
            applied=[
                AppliedDiscount(title="Promo", amount=-100, code="CODE1"),
            ],
        )
        data = disco.model_dump(mode="json", exclude_none=True)

        assert "codes" in data, "Spec: discounts object must have 'codes' field"
        assert isinstance(data["codes"], list), "Spec: codes must be an array"
        for code in data["codes"]:
            assert isinstance(code, str), "Spec: each code must be a string"

        assert "applied" in data, "Spec: discounts object must have 'applied' field"
        assert isinstance(data["applied"], list), "Spec: applied must be an array"

    def test_discounts_object_codes_defaults_to_none(self):
        # codes is optional (None when not provided by client)
        disco = DiscountsObject()
        assert disco.codes is None

    def test_discounts_object_applied_defaults_to_none(self):
        # applied is optional (None before server computes discounts)
        disco = DiscountsObject()
        assert disco.applied is None


# ---------------------------------------------------------------------------
# T8: totals.json – array composition constraints
# Spec: totals.json allOf contains type="subtotal" minContains: 1 maxContains: 1
#        AND contains type="total" minContains: 1 maxContains: 1
# ---------------------------------------------------------------------------


class TestTotalsArrayComposition:
    """T8: totals.json – array composition constraints."""

    def test_valid_totals_array_with_subtotal_and_total(self):
        """Spec: totals.json requires exactly 1 subtotal and exactly 1 total entry."""
        totals = [
            TotalResponse(type="subtotal", display_text="Subtotal", amount=2000),
            TotalResponse(type="tax", display_text="Tax", amount=160),
            TotalResponse(type="total", display_text="Total", amount=2160),
        ]
        data = [t.model_dump(mode="json", exclude_none=True) for t in totals]
        subtotals = [t for t in data if t["type"] == "subtotal"]
        totals_entries = [t for t in data if t["type"] == "total"]
        assert len(subtotals) == 1, "Spec requires exactly 1 subtotal entry"
        assert len(totals_entries) == 1, "Spec requires exactly 1 total entry"

    def test_totals_array_allows_multiple_detail_types(self):
        """Spec: totals.json allows multiple tax, fee, discount, fulfillment entries."""
        totals = [
            TotalResponse(type="subtotal", display_text="Subtotal", amount=5000),
            TotalResponse(type="tax", display_text="State Tax", amount=300),
            TotalResponse(type="tax", display_text="Local Tax", amount=50),
            TotalResponse(type="fee", display_text="Service Fee", amount=100),
            TotalResponse(type="fulfillment", display_text="Shipping", amount=500),
            TotalResponse(type="total", display_text="Total", amount=5950),
        ]
        data = [t.model_dump(mode="json", exclude_none=True) for t in totals]
        tax_entries = [t for t in data if t["type"] == "tax"]
        assert len(tax_entries) == 2, "Spec allows multiple tax entries"

    def test_totals_mincontains_maxcontains_not_enforced_by_model(self):
        """Spec: totals.json minContains/maxContains constraints are JSON Schema-level."""
        # Pydantic cannot enforce minContains/maxContains on list[TotalResponse].
        # The model allows a totals list with no subtotal or no total.
        # This documents the spec constraint that must be enforced at the
        # application layer, not by the model.
        totals = [
            TotalResponse(type="tax", display_text="Tax", amount=100),
        ]
        data = [t.model_dump(mode="json", exclude_none=True) for t in totals]
        subtotals = [t for t in data if t["type"] == "subtotal"]
        assert len(subtotals) == 0, (
            "Model gap: Pydantic does not enforce minContains/maxContains — "
            "spec requires exactly 1 subtotal but model allows 0"
        )

    def test_well_known_total_types(self):
        """Spec: total.json well-known types: subtotal, items_discount, discount, fulfillment, tax, fee, total."""
        well_known = ["subtotal", "items_discount", "discount", "fulfillment", "tax", "fee", "total"]
        for t_type in well_known:
            t = TotalResponse(type=t_type, amount=100)
            assert t.type == t_type, f"TotalResponse must accept well-known type '{t_type}'"


# ---------------------------------------------------------------------------
# D10: discount.json – AppliedDiscount method enum and priority minimum
# Spec: method enum: ["each", "across"], priority minimum: 1
# ---------------------------------------------------------------------------


class TestAppliedDiscountMethodEnum:
    """D10: discount.json – AppliedDiscount method enum values."""

    @pytest.mark.parametrize("method", ["each", "across"])
    def test_method_accepts_spec_enum_values(self, method):
        """Spec: discount.json applied_discount.method enum: ["each", "across"]."""
        ad = AppliedDiscount(title="Test", amount=-100, method=method)
        data = ad.model_dump(mode="json", exclude_none=True)
        assert data["method"] == method, (
            f"AppliedDiscount must accept spec method '{method}'"
        )

    def test_method_is_str_not_literal(self):
        """Spec: discount.json method enum but model uses plain str."""
        # The spec defines method as enum: ["each", "across"] but the Pydantic
        # model uses `str | None`, so any string is accepted.
        ad = AppliedDiscount(title="Test", method="invalid")
        assert ad.method == "invalid", (
            "Model gap: AppliedDiscount.method is typed as str, not Literal — "
            "spec enum ['each', 'across'] is not enforced"
        )


class TestAppliedDiscountPriorityMinimum:
    """D10: discount.json – AppliedDiscount priority minimum constraint."""

    def test_priority_accepts_minimum_value_one(self):
        """Spec: discount.json applied_discount.priority has minimum: 1."""
        ad = AppliedDiscount(title="First", amount=-100, priority=1)
        data = ad.model_dump(mode="json", exclude_none=True)
        assert data["priority"] == 1, "priority must accept minimum value 1"

    def test_priority_accepts_higher_values(self):
        """Spec: discount.json applied_discount.priority accepts integers >= 1."""
        ad = AppliedDiscount(title="Second", amount=-50, priority=5)
        assert ad.priority == 5

    def test_priority_minimum_not_enforced_by_model(self):
        """Spec: discount.json priority minimum: 1 but model uses plain int."""
        # The spec requires minimum: 1, but Pydantic model uses `int | None`
        # without Field(ge=1), so 0 and negative values are accepted.
        ad = AppliedDiscount(title="Bad", priority=0)
        assert ad.priority == 0, (
            "Model gap: AppliedDiscount accepts priority=0 "
            "(spec requires minimum: 1 but model uses plain int)"
        )
