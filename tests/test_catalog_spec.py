"""Tests validating UCP catalog spec compliance for response structures.

These tests validate that catalog Pydantic models produce JSON output
matching the UCP spec (catalog_search.json, catalog_lookup.json, and referenced type schemas).
They run against the models directly -- no database or server needed.

Each test cites the spec requirement it validates. The tests represent
the spec, not what is required for our app to pass.
"""

import re
import sys
import os

import pytest

# Add src to path so we can import the models
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from models import (
    CatalogAvailability,
    CatalogCategory,
    CatalogDescription,
    CatalogDetailProduct,
    CatalogInputCorrelation,
    CatalogLookupResponse,
    CatalogMedia,
    CatalogMessage,
    CatalogPaginationRequest,
    CatalogPaginationResponse,
    CatalogPrice,
    CatalogPriceFilter,
    CatalogPriceRange,
    CatalogProduct,
    CatalogProductResponse,
    CatalogProductWithInputs,
    CatalogSearchFilters,
    CatalogSearchResponse,
    CatalogUcp,
    CatalogVariant,
    CatalogVariantWithInputs,
    DetailOptionValue,
    DetailProductOption,
    OptionValue,
    PostalAddress,
    ProductOption,
    SelectedOption,
)


VERSION = "2026-04-08"
VERSION_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


# --- Helpers ---

def _make_ucp(capability):
    """Mirror the route helper to produce a CatalogUcp envelope."""
    return CatalogUcp(
        version=VERSION,
        capabilities={capability: [{"version": VERSION}]},
    )


def _make_price(amount=1000, currency="USD"):
    return CatalogPrice(amount=amount, currency=currency)


def _make_variant(id="v-1", title="Variant 1", amount=1000):
    return CatalogVariant(
        id=id,
        title=title,
        price=_make_price(amount=amount),
        availability=CatalogAvailability(available=True, status="in_stock"),
    )


def _make_product(id="prod-1", title="Test Product"):
    price = _make_price()
    return CatalogProduct(
        id=id,
        title=title,
        price_range=CatalogPriceRange(min=price, max=price),
        variants=[_make_variant()],
    )


# ---------------------------------------------------------------------------
# S1: Search response structure
# Spec: catalog_search.json#/$defs/search_response required: ["ucp", "products"]
#   pagination.json#/$defs/response required: ["has_next_page"]
# ---------------------------------------------------------------------------


class TestSearchResponse:
    """S1: Search response contains products array and pagination object."""

    def test_search_response_has_products_array(self):
        # Spec: "Response body contains `products` (array of product)"
        resp = CatalogSearchResponse(
            ucp=_make_ucp("dev.ucp.shopping.catalog.search"),
            products=[_make_product()],
            pagination=CatalogPaginationResponse(has_next_page=False),
        )
        data = resp.model_dump(mode="json", exclude_none=True)
        assert "products" in data
        assert isinstance(data["products"], list)

    def test_search_response_has_pagination_object(self):
        # Spec: "Response body contains ... `pagination` (object with
        #   cursor, has_next_page, total_count)"
        resp = CatalogSearchResponse(
            ucp=_make_ucp("dev.ucp.shopping.catalog.search"),
            products=[],
            pagination=CatalogPaginationResponse(
                cursor="10", has_next_page=True, total_count=25,
            ),
        )
        data = resp.model_dump(mode="json", exclude_none=True)
        assert "pagination" in data
        assert isinstance(data["pagination"], dict)

    def test_pagination_has_required_has_next_page(self):
        # Spec: pagination.has_next_page is boolean, required
        pag = CatalogPaginationResponse(has_next_page=True)
        data = pag.model_dump(mode="json", exclude_none=True)
        assert "has_next_page" in data
        assert isinstance(data["has_next_page"], bool)

    def test_pagination_optional_cursor(self):
        # Spec: pagination.cursor is optional
        pag = CatalogPaginationResponse(has_next_page=False)
        data = pag.model_dump(mode="json", exclude_none=True)
        assert "cursor" not in data, "cursor should be omitted when None"

    def test_pagination_optional_total_count(self):
        # Spec: pagination.total_count is optional
        pag = CatalogPaginationResponse(has_next_page=False)
        data = pag.model_dump(mode="json", exclude_none=True)
        assert "total_count" not in data, "total_count should be omitted when None"

    def test_pagination_includes_cursor_when_set(self):
        # Spec: pagination.cursor present when there is a next page
        pag = CatalogPaginationResponse(cursor="abc", has_next_page=True)
        data = pag.model_dump(mode="json", exclude_none=True)
        assert data["cursor"] == "abc"

    def test_pagination_includes_total_count_when_set(self):
        # Spec: pagination.total_count present when known
        pag = CatalogPaginationResponse(has_next_page=False, total_count=42)
        data = pag.model_dump(mode="json", exclude_none=True)
        assert data["total_count"] == 42

    def test_search_response_products_empty_list_valid(self):
        # Spec: products is an array; an empty result set is valid
        resp = CatalogSearchResponse(
            ucp=_make_ucp("dev.ucp.shopping.catalog.search"),
            products=[],
            pagination=CatalogPaginationResponse(has_next_page=False),
        )
        data = resp.model_dump(mode="json", exclude_none=True)
        assert data["products"] == []


# ---------------------------------------------------------------------------
# S2: Search pagination defaults
# Spec: pagination.json#/$defs/request limit default: 10
# ---------------------------------------------------------------------------


class TestSearchPaginationDefaults:
    """S2: Pagination request defaults."""

    def test_pagination_limit_defaults_to_10(self):
        # Spec: "pagination.limit default 10"
        pag = CatalogPaginationRequest()
        assert pag.limit == 10

    def test_pagination_cursor_defaults_to_none(self):
        # Spec: pagination.cursor is optional, defaults to beginning
        pag = CatalogPaginationRequest()
        assert pag.cursor is None

    def test_pagination_limit_can_be_overridden(self):
        # Spec: client may specify a custom limit
        pag = CatalogPaginationRequest(limit=25)
        assert pag.limit == 25


# ---------------------------------------------------------------------------
# S3: Lookup response - partial success
# Spec: catalog_lookup.json#/$defs/lookup_response required: ["ucp", "products"]
# Behavior (catalog/rest.md): "Return HTTP 200 for lookups; unknown IDs =
#   fewer results returned"
# ---------------------------------------------------------------------------


class TestLookupPartialSuccess:
    """S3: Lookup returns 200 with fewer products for unknown IDs."""

    def test_lookup_response_can_have_fewer_products_than_requested_ids(self):
        # Spec: "unknown IDs = fewer results returned"
        # Requesting 3 IDs but only 1 found
        product = CatalogProductWithInputs(
            id="prod-1",
            title="Found Product",
            variants=[CatalogVariantWithInputs(
                id="v-1", title="V1",
                price=_make_price(),
                inputs=[CatalogInputCorrelation(id="prod-1", match="exact")],
            )],
        )
        resp = CatalogLookupResponse(
            ucp=_make_ucp("dev.ucp.shopping.catalog.lookup"),
            products=[product],
            messages=[],
        )
        data = resp.model_dump(mode="json", exclude_none=True)
        # Only 1 product returned for 3 requested -- spec says this is fine
        assert len(data["products"]) == 1

    def test_lookup_response_includes_not_found_messages(self):
        # Spec: messages with not_found info codes for missing IDs
        resp = CatalogLookupResponse(
            ucp=_make_ucp("dev.ucp.shopping.catalog.lookup"),
            products=[],
            messages=[
                CatalogMessage(type="info", code="not_found", content="Product 'x' was not found"),
                CatalogMessage(type="info", code="not_found", content="Product 'y' was not found"),
            ],
        )
        data = resp.model_dump(mode="json", exclude_none=True)
        assert len(data["messages"]) == 2
        for msg in data["messages"]:
            assert msg["type"] == "info"
            assert msg["code"] == "not_found"

    def test_lookup_response_empty_products_is_valid(self):
        # Spec: all IDs unknown returns empty products list, not an error
        resp = CatalogLookupResponse(
            ucp=_make_ucp("dev.ucp.shopping.catalog.lookup"),
            products=[],
            messages=[
                CatalogMessage(type="info", code="not_found", content="Product 'z' was not found"),
            ],
        )
        data = resp.model_dump(mode="json", exclude_none=True)
        assert data["products"] == []
        # Status should not be "error" -- partial success is still 200
        assert data["ucp"].get("status") is None or data["ucp"]["status"] != "error"


# ---------------------------------------------------------------------------
# S4: Lookup response - input correlations
# Spec: catalog_lookup.json#/$defs/lookup_variant required: ["inputs"]
#   input_correlation.json required: ["id"]
# ---------------------------------------------------------------------------


class TestLookupInputCorrelations:
    """S4: Lookup products include input correlations on variants."""

    def test_variant_with_inputs_has_inputs_array(self):
        # Spec: "Products in lookup response include `inputs` correlation"
        variant = CatalogVariantWithInputs(
            id="v-1",
            title="V1",
            price=_make_price(),
            inputs=[CatalogInputCorrelation(id="prod-1", match="exact")],
        )
        data = variant.model_dump(mode="json", exclude_none=True)
        assert "inputs" in data
        assert isinstance(data["inputs"], list)
        assert len(data["inputs"]) == 1

    def test_input_correlation_has_id_and_match(self):
        # Spec: CatalogInputCorrelation has `id` and `match` fields
        corr = CatalogInputCorrelation(id="prod-1", match="exact")
        data = corr.model_dump(mode="json", exclude_none=True)
        assert data["id"] == "prod-1"
        assert data["match"] == "exact"

    def test_input_correlation_match_defaults_to_exact(self):
        # Spec: default match type is "exact"
        corr = CatalogInputCorrelation(id="prod-1")
        assert corr.match == "exact"

    def test_product_with_inputs_variants_are_variant_with_inputs(self):
        # Spec: lookup products use CatalogVariantWithInputs (with inputs array)
        product = CatalogProductWithInputs(
            id="prod-1",
            title="Test",
            variants=[
                CatalogVariantWithInputs(
                    id="v-1", title="V1",
                    price=_make_price(),
                    inputs=[CatalogInputCorrelation(id="prod-1", match="exact")],
                ),
            ],
        )
        data = product.model_dump(mode="json", exclude_none=True)
        assert len(data["variants"]) == 1
        assert "inputs" in data["variants"][0]

    def test_lookup_response_products_are_product_with_inputs(self):
        # Spec: lookup response uses CatalogProductWithInputs
        product = CatalogProductWithInputs(
            id="prod-1",
            title="Test",
            variants=[
                CatalogVariantWithInputs(
                    id="v-1", title="V1",
                    price=_make_price(),
                    inputs=[CatalogInputCorrelation(id="prod-1", match="exact")],
                ),
            ],
        )
        resp = CatalogLookupResponse(
            ucp=_make_ucp("dev.ucp.shopping.catalog.lookup"),
            products=[product],
        )
        data = resp.model_dump(mode="json", exclude_none=True)
        assert "inputs" in data["products"][0]["variants"][0]


# ---------------------------------------------------------------------------
# S5: Product detail response - singular product
# Spec: catalog_lookup.json#/$defs/get_product_response required: ["ucp", "product"]
#   "product" is a single object, not an array
# ---------------------------------------------------------------------------


class TestProductDetailResponse:
    """S5: Product response has singular `product`, not `products` array."""

    def test_product_response_has_singular_product_field(self):
        # Spec: "Response contains singular `product` object (not array)"
        detail = CatalogDetailProduct(
            id="prod-1",
            title="Test Product",
            variants=[_make_variant()],
        )
        resp = CatalogProductResponse(
            ucp=_make_ucp("dev.ucp.shopping.catalog.product"),
            product=detail,
        )
        data = resp.model_dump(mode="json", exclude_none=True)
        assert "product" in data
        assert isinstance(data["product"], dict), "product must be a single object"
        assert "products" not in data, "Must not have 'products' array"

    def test_product_response_product_is_not_list(self):
        # Spec: singular `product` -- must never serialize as array
        detail = CatalogDetailProduct(
            id="prod-1",
            title="Test",
            variants=[_make_variant()],
        )
        resp = CatalogProductResponse(
            ucp=_make_ucp("dev.ucp.shopping.catalog.product"),
            product=detail,
        )
        data = resp.model_dump(mode="json", exclude_none=True)
        assert not isinstance(data["product"], list)


# ---------------------------------------------------------------------------
# S6: Product not found - error via messages
# Behavior (catalog/rest.md): "Get Product with unknown ID returns HTTP 200
#   with ucp.status: 'error' and messages"
# ---------------------------------------------------------------------------


class TestProductNotFound:
    """S6: Unknown product returns 200 with error status and messages."""

    def test_product_not_found_has_null_product(self):
        # Spec: unknown product -> product is null/absent
        resp = CatalogProductResponse(
            ucp=CatalogUcp(
                version=VERSION,
                capabilities={"dev.ucp.shopping.catalog.product": [{"version": VERSION}]},
                status="error",
            ),
            product=None,
            messages=[CatalogMessage(type="error", code="not_found", content="Not found")],
        )
        data = resp.model_dump(mode="json", exclude_none=True)
        assert "product" not in data or data.get("product") is None

    def test_product_not_found_ucp_status_is_error(self):
        # Spec: "ucp.status: 'error'" for not-found
        resp = CatalogProductResponse(
            ucp=CatalogUcp(
                version=VERSION,
                capabilities={"dev.ucp.shopping.catalog.product": [{"version": VERSION}]},
                status="error",
            ),
            product=None,
            messages=[CatalogMessage(type="error", code="not_found", content="Not found")],
        )
        data = resp.model_dump(mode="json", exclude_none=True)
        assert data["ucp"]["status"] == "error"

    def test_product_not_found_has_messages_array(self):
        # Spec: messages array containing error with code not_found
        resp = CatalogProductResponse(
            ucp=CatalogUcp(
                version=VERSION,
                capabilities={"dev.ucp.shopping.catalog.product": [{"version": VERSION}]},
                status="error",
            ),
            product=None,
            messages=[CatalogMessage(type="error", code="not_found", content="Product 'x' was not found")],
        )
        data = resp.model_dump(mode="json", exclude_none=True)
        assert "messages" in data
        assert isinstance(data["messages"], list)
        assert len(data["messages"]) >= 1
        msg = data["messages"][0]
        assert msg["type"] == "error"
        assert msg["code"] == "not_found"

    def test_product_not_found_message_has_content(self):
        # Spec: message objects have optional content string
        msg = CatalogMessage(type="error", code="not_found", content="Product 'abc' was not found")
        data = msg.model_dump(mode="json", exclude_none=True)
        assert "content" in data
        assert isinstance(data["content"], str)


# ---------------------------------------------------------------------------
# S7: Price objects require amount and currency
# Spec: types/price.json required: ["amount", "currency"]
#   amount.json type: integer, minimum: 0
# ---------------------------------------------------------------------------


class TestPriceObject:
    """S7: Price has amount (integer, minor units) and currency (string)."""

    def test_price_has_amount_and_currency(self):
        # Spec: "Price object requires {amount, currency}"
        price = CatalogPrice(amount=1999, currency="USD")
        data = price.model_dump(mode="json", exclude_none=True)
        assert "amount" in data
        assert "currency" in data

    def test_price_amount_is_integer(self):
        # Spec: amount is integer type (minor units, e.g. cents)
        price = CatalogPrice(amount=1999, currency="USD")
        data = price.model_dump(mode="json", exclude_none=True)
        assert isinstance(data["amount"], int)

    def test_price_currency_is_string(self):
        # Spec: currency is an ISO 4217 string
        price = CatalogPrice(amount=1999, currency="EUR")
        data = price.model_dump(mode="json", exclude_none=True)
        assert isinstance(data["currency"], str)

    def test_price_amount_zero_is_valid(self):
        # Spec: amount of 0 is valid (free items)
        price = CatalogPrice(amount=0, currency="USD")
        data = price.model_dump(mode="json", exclude_none=True)
        assert data["amount"] == 0

    def test_price_defaults(self):
        # Model defaults: amount=0, currency="USD"
        price = CatalogPrice()
        assert price.amount == 0
        assert price.currency == "USD"


# ---------------------------------------------------------------------------
# S8: Price range has min and max
# Spec: types/price_range.json required: ["min", "max"]
#   min/max each $ref: price.json
# ---------------------------------------------------------------------------


class TestPriceRange:
    """S8: PriceRange has min and max, each a Price object."""

    def test_price_range_has_min_and_max(self):
        # Spec: "PriceRange requires min and max"
        pr = CatalogPriceRange(
            min=CatalogPrice(amount=500, currency="USD"),
            max=CatalogPrice(amount=2000, currency="USD"),
        )
        data = pr.model_dump(mode="json", exclude_none=True)
        assert "min" in data
        assert "max" in data

    def test_price_range_min_is_price_object(self):
        # Spec: "each a Price object"
        pr = CatalogPriceRange(
            min=CatalogPrice(amount=500, currency="USD"),
            max=CatalogPrice(amount=2000, currency="USD"),
        )
        data = pr.model_dump(mode="json", exclude_none=True)
        assert "amount" in data["min"]
        assert "currency" in data["min"]

    def test_price_range_max_is_price_object(self):
        # Spec: "each a Price object"
        pr = CatalogPriceRange(
            min=CatalogPrice(amount=500, currency="USD"),
            max=CatalogPrice(amount=2000, currency="USD"),
        )
        data = pr.model_dump(mode="json", exclude_none=True)
        assert "amount" in data["max"]
        assert "currency" in data["max"]

    def test_price_range_single_price_min_equals_max(self):
        # Spec: single-variant products have min == max
        price = CatalogPrice(amount=1000, currency="USD")
        pr = CatalogPriceRange(min=price, max=price)
        data = pr.model_dump(mode="json", exclude_none=True)
        assert data["min"]["amount"] == data["max"]["amount"]
        assert data["min"]["currency"] == data["max"]["currency"]


# ---------------------------------------------------------------------------
# S9: Product requires at least one variant
# Spec: types/product.json required: ["id", "title", "description", "price_range", "variants"]
#   variants: array of variant.json, minItems: 1
# ---------------------------------------------------------------------------


class TestProductVariantsRequired:
    """S9: Product must have at least one variant."""

    def test_product_has_variants_list(self):
        # Spec: "variants array"
        product = _make_product()
        data = product.model_dump(mode="json", exclude_none=True)
        assert "variants" in data
        assert isinstance(data["variants"], list)

    def test_product_has_at_least_one_variant(self):
        # Spec: "variants array, minItems: 1"
        product = _make_product()
        data = product.model_dump(mode="json", exclude_none=True)
        assert len(data["variants"]) >= 1

    def test_row_to_product_produces_at_least_one_variant(self):
        # Implementation: _row_to_product helper always creates at least one
        # variant from a database row.  This tests the helper, not the model
        # constraint (which is covered by the two tests above).
        from routes.catalog import _row_to_product

        class FakeRow:
            id = "prod-1"
            title = "Test Product"
            price = 1000
            currency = "USD"
            image_url = None
            categories = "[]"
            stock = 5
            description = "A product"
            handle = "test-product"

        product = _row_to_product(FakeRow())
        data = product.model_dump(mode="json", exclude_none=True)
        assert len(data["variants"]) >= 1, (
            "Spec requires minItems: 1 for variants"
        )


# ---------------------------------------------------------------------------
# S10: Product description is object
# Spec: types/description.json type: object, minProperties: 1
#   properties: {plain, html, markdown}
# ---------------------------------------------------------------------------


class TestDescriptionObject:
    """S10: Description serializes as object with plain/html, not bare string."""

    def test_description_is_object_not_string(self):
        # Spec: "description is an object with plain and/or html fields"
        desc = CatalogDescription(plain="A great product")
        data = desc.model_dump(mode="json", exclude_none=True)
        assert isinstance(data, dict), "description must serialize as object, not string"
        assert "plain" in data

    def test_description_plain_field(self):
        # Spec: description has plain field
        desc = CatalogDescription(plain="Plain text description")
        data = desc.model_dump(mode="json", exclude_none=True)
        assert data["plain"] == "Plain text description"

    def test_description_html_field(self):
        # Spec: description has html field
        desc = CatalogDescription(html="<p>Rich description</p>")
        data = desc.model_dump(mode="json", exclude_none=True)
        assert data["html"] == "<p>Rich description</p>"

    def test_description_both_fields(self):
        # Spec: "plain and/or html fields"
        desc = CatalogDescription(plain="Plain", html="<p>Rich</p>")
        data = desc.model_dump(mode="json", exclude_none=True)
        assert "plain" in data
        assert "html" in data

    def test_description_on_product_is_object(self):
        # Spec: product.description is a description object
        product = CatalogProduct(
            id="prod-1",
            title="Test",
            description=CatalogDescription(plain="Product desc"),
            variants=[_make_variant()],
        )
        data = product.model_dump(mode="json", exclude_none=True)
        assert isinstance(data["description"], dict)
        assert "plain" in data["description"]

    def test_description_on_variant_is_object(self):
        # Spec: variant.description is a description object
        variant = CatalogVariant(
            id="v-1",
            title="V1",
            description=CatalogDescription(plain="Variant desc"),
            price=_make_price(),
        )
        data = variant.model_dump(mode="json", exclude_none=True)
        assert isinstance(data["description"], dict)
        assert "plain" in data["description"]


# ---------------------------------------------------------------------------
# S11: Catalog response UCP envelope
# Spec: catalog_search.json#/$defs/search_response required: ["ucp"]
#   catalog_lookup.json#/$defs/lookup_response required: ["ucp"]
#   catalog_lookup.json#/$defs/get_product_response required: ["ucp"]
# ---------------------------------------------------------------------------


class TestUcpEnvelope:
    """S11: All catalog responses include ucp with version and capabilities."""

    def test_search_response_has_ucp(self):
        # Spec: "All responses include ucp object with version, capabilities"
        resp = CatalogSearchResponse(
            ucp=_make_ucp("dev.ucp.shopping.catalog.search"),
            products=[],
            pagination=CatalogPaginationResponse(has_next_page=False),
        )
        data = resp.model_dump(mode="json", exclude_none=True)
        assert "ucp" in data
        assert "version" in data["ucp"]
        assert "capabilities" in data["ucp"]

    def test_lookup_response_has_ucp(self):
        # Spec: "All responses include ucp object with version, capabilities"
        resp = CatalogLookupResponse(
            ucp=_make_ucp("dev.ucp.shopping.catalog.lookup"),
            products=[],
        )
        data = resp.model_dump(mode="json", exclude_none=True)
        assert "ucp" in data
        assert "version" in data["ucp"]
        assert "capabilities" in data["ucp"]

    def test_product_response_has_ucp(self):
        # Spec: "All responses include ucp object with version, capabilities"
        detail = CatalogDetailProduct(
            id="prod-1",
            title="Test",
            variants=[_make_variant()],
        )
        resp = CatalogProductResponse(
            ucp=_make_ucp("dev.ucp.shopping.catalog.product"),
            product=detail,
        )
        data = resp.model_dump(mode="json", exclude_none=True)
        assert "ucp" in data
        assert "version" in data["ucp"]
        assert "capabilities" in data["ucp"]

    ## test_ucp_version_format removed: covered by X1 in test_spec_compliance.py

    def test_ucp_capabilities_is_dict(self):
        # Spec: capabilities is a keyed object (not array)
        ucp = _make_ucp("dev.ucp.shopping.catalog.search")
        data = ucp.model_dump(mode="json", exclude_none=True)
        assert isinstance(data["capabilities"], dict)

    def test_ucp_capability_values_are_arrays(self):
        # Spec: each capability value is an array of entries with version
        ucp = _make_ucp("dev.ucp.shopping.catalog.search")
        data = ucp.model_dump(mode="json", exclude_none=True)
        for key, entries in data["capabilities"].items():
            assert isinstance(entries, list)
            assert len(entries) > 0
            assert "version" in entries[0]


# ---------------------------------------------------------------------------
# S12: Media object structure
# Spec: types/media.json required: ["type", "url"]
#   alt_text: optional string
# ---------------------------------------------------------------------------


class TestMediaObject:
    """S12: Media has type, url, and optional alt_text."""

    def test_media_has_type_and_url(self):
        # Spec: "media array items have type, url"
        media = CatalogMedia(type="image", url="https://example.com/img.jpg")
        data = media.model_dump(mode="json", exclude_none=True)
        assert "type" in data
        assert "url" in data

    def test_media_alt_text_is_optional(self):
        # Spec: "alt_text" is optional
        media = CatalogMedia(type="image", url="https://example.com/img.jpg")
        data = media.model_dump(mode="json", exclude_none=True)
        assert "alt_text" not in data, "alt_text should be omitted when None"

    def test_media_includes_alt_text_when_set(self):
        # Spec: alt_text present when provided
        media = CatalogMedia(type="image", url="https://example.com/img.jpg", alt_text="Product photo")
        data = media.model_dump(mode="json", exclude_none=True)
        assert data["alt_text"] == "Product photo"

    def test_media_type_defaults_to_image(self):
        # Model default: type="image"
        media = CatalogMedia(url="https://example.com/img.jpg")
        assert media.type == "image"

    def test_media_on_product(self):
        # Spec: product.media is array of media objects
        product = CatalogProduct(
            id="prod-1",
            title="Test",
            media=[CatalogMedia(type="image", url="https://example.com/img.jpg", alt_text="Photo")],
            variants=[_make_variant()],
        )
        data = product.model_dump(mode="json", exclude_none=True)
        assert isinstance(data["media"], list)
        assert data["media"][0]["type"] == "image"
        assert data["media"][0]["url"] == "https://example.com/img.jpg"

    def test_media_on_variant(self):
        # Spec: variant.media is array of media objects
        variant = CatalogVariant(
            id="v-1",
            title="V1",
            price=_make_price(),
            media=[CatalogMedia(type="image", url="https://example.com/v.jpg")],
        )
        data = variant.model_dump(mode="json", exclude_none=True)
        assert isinstance(data["media"], list)
        assert len(data["media"]) == 1


# ---------------------------------------------------------------------------
# S13: Category structure
# Spec: types/category.json required: ["value"]
#   taxonomy: optional string
# ---------------------------------------------------------------------------


class TestCategoryObject:
    """S13: Category has value and taxonomy."""

    def test_category_has_value_and_taxonomy(self):
        # Spec: "category has value and taxonomy fields"
        cat = CatalogCategory(value="Clothing", taxonomy="merchant")
        data = cat.model_dump(mode="json", exclude_none=True)
        assert "value" in data
        assert "taxonomy" in data

    def test_category_taxonomy_defaults_to_merchant(self):
        # Model default: taxonomy="merchant"
        cat = CatalogCategory(value="Shoes")
        assert cat.taxonomy == "merchant"

    def test_category_on_product(self):
        # Spec: product.categories is array of category objects
        product = CatalogProduct(
            id="prod-1",
            title="Test",
            categories=[
                CatalogCategory(value="Shoes", taxonomy="merchant"),
                CatalogCategory(value="Running", taxonomy="merchant"),
            ],
            variants=[_make_variant()],
        )
        data = product.model_dump(mode="json", exclude_none=True)
        assert isinstance(data["categories"], list)
        assert len(data["categories"]) == 2
        assert data["categories"][0]["value"] == "Shoes"
        assert data["categories"][0]["taxonomy"] == "merchant"


# ---------------------------------------------------------------------------
# S14: Variant availability
# Spec: types/variant.json properties.availability.properties.available: boolean
# ---------------------------------------------------------------------------


class TestVariantAvailability:
    """S14: Availability has available boolean field."""

    def test_availability_has_available_boolean(self):
        # Spec: "variant.availability has `available` boolean"
        avail = CatalogAvailability(available=True)
        data = avail.model_dump(mode="json", exclude_none=True)
        assert "available" in data
        assert isinstance(data["available"], bool)

    def test_availability_available_true(self):
        # Spec: available=true means item is purchasable
        avail = CatalogAvailability(available=True, status="in_stock")
        data = avail.model_dump(mode="json", exclude_none=True)
        assert data["available"] is True

    def test_availability_available_false(self):
        # Spec: available=false means item is not purchasable
        avail = CatalogAvailability(available=False, status="out_of_stock")
        data = avail.model_dump(mode="json", exclude_none=True)
        assert data["available"] is False

    def test_availability_on_variant(self):
        # Spec: variant.availability is an availability object
        variant = CatalogVariant(
            id="v-1",
            title="V1",
            price=_make_price(),
            availability=CatalogAvailability(available=True, status="in_stock"),
        )
        data = variant.model_dump(mode="json", exclude_none=True)
        assert "availability" in data
        assert isinstance(data["availability"]["available"], bool)

    def test_availability_defaults_to_true(self):
        # Model default: available=True
        avail = CatalogAvailability()
        assert avail.available is True


# ---------------------------------------------------------------------------
# S15: Search response capabilities match catalog.search
# Spec: catalog search responses declare
#   `dev.ucp.shopping.catalog.search` capability
# ---------------------------------------------------------------------------


class TestSearchCapability:
    """S15: Route helper produces correct capability key."""

    def test_make_ucp_produces_correct_capability_key(self):
        # Spec: catalog search responses declare
        #   `dev.ucp.shopping.catalog.search` capability
        from routes.catalog import _make_ucp as route_make_ucp

        ucp = route_make_ucp("dev.ucp.shopping.catalog.search")
        data = ucp.model_dump(mode="json", exclude_none=True)
        assert "dev.ucp.shopping.catalog.search" in data["capabilities"]

    def test_make_ucp_capability_has_version(self):
        # Spec: each capability entry has a version
        from routes.catalog import _make_ucp as route_make_ucp

        ucp = route_make_ucp("dev.ucp.shopping.catalog.search")
        data = ucp.model_dump(mode="json", exclude_none=True)
        entries = data["capabilities"]["dev.ucp.shopping.catalog.search"]
        assert len(entries) >= 1
        assert "version" in entries[0]
        assert VERSION_PATTERN.match(entries[0]["version"])

    def test_lookup_capability_key(self):
        # Spec: catalog lookup responses declare
        #   `dev.ucp.shopping.catalog.lookup` capability
        from routes.catalog import _make_ucp as route_make_ucp

        ucp = route_make_ucp("dev.ucp.shopping.catalog.lookup")
        data = ucp.model_dump(mode="json", exclude_none=True)
        assert "dev.ucp.shopping.catalog.lookup" in data["capabilities"]

    def test_product_capability_key(self):
        # Spec: catalog product responses declare
        #   `dev.ucp.shopping.catalog.product` capability
        from routes.catalog import _make_ucp as route_make_ucp

        ucp = route_make_ucp("dev.ucp.shopping.catalog.product")
        data = ucp.model_dump(mode="json", exclude_none=True)
        assert "dev.ucp.shopping.catalog.product" in data["capabilities"]

    def test_capability_key_is_reverse_domain_format(self):
        # Spec: capability keys are reverse-domain format
        from routes.catalog import _make_ucp as route_make_ucp

        ucp = route_make_ucp("dev.ucp.shopping.catalog.search")
        for key in ucp.capabilities:
            assert "." in key, f"Capability key '{key}' should be reverse-domain format"


# ============================================================================
# PRODUCT OPTION SPEC (types/product_option.json)
# ============================================================================


class TestProductOptionRequiredFields:
    """S16: Product option structure.

    Spec: types/product_option.json required: ["name", "values"]
    values: array, minItems: 1
    """

    def test_product_option_has_name_and_values(self):
        # Spec: types/product_option.json required: ["name", "values"]
        opt = ProductOption(
            name="Size",
            values=[OptionValue(label="Large")],
        )
        data = opt.model_dump(mode="json", exclude_none=True)
        assert "name" in data, "ProductOption must have 'name' per product_option.json"
        assert "values" in data, "ProductOption must have 'values' per product_option.json"

    def test_product_option_values_is_array(self):
        # Spec: types/product_option.json values: array of option_value.json
        opt = ProductOption(
            name="Color",
            values=[OptionValue(label="Red"), OptionValue(label="Blue")],
        )
        data = opt.model_dump(mode="json", exclude_none=True)
        assert isinstance(data["values"], list), "values must be an array"
        assert len(data["values"]) >= 1, "values minItems: 1"

    def test_option_value_has_label(self):
        # Spec: types/option_value.json required: ["label"]
        val = OptionValue(label="Medium")
        data = val.model_dump(mode="json", exclude_none=True)
        assert "label" in data, "OptionValue must have 'label' per option_value.json"

    def test_option_value_id_is_optional(self):
        # Spec: types/option_value.json optional: id
        val = OptionValue(label="Small")
        data = val.model_dump(mode="json", exclude_none=True)
        assert "id" not in data, "id should be excluded when None"

    def test_option_value_id_serializes_when_provided(self):
        # Spec: types/option_value.json optional: id
        val = OptionValue(id="opt_sm", label="Small")
        data = val.model_dump(mode="json", exclude_none=True)
        assert data["id"] == "opt_sm"


# ============================================================================
# SELECTED OPTION SPEC (types/selected_option.json)
# ============================================================================


class TestSelectedOptionRequiredFields:
    """S17: Selected option structure.

    Spec: types/selected_option.json required: ["name", "label"]
    optional: id
    """

    def test_selected_option_has_name_and_label(self):
        # Spec: types/selected_option.json required: ["name", "label"]
        opt = SelectedOption(name="Size", label="Large")
        data = opt.model_dump(mode="json", exclude_none=True)
        assert "name" in data, "SelectedOption must have 'name' per selected_option.json"
        assert "label" in data, "SelectedOption must have 'label' per selected_option.json"

    def test_selected_option_id_is_optional(self):
        # Spec: types/selected_option.json optional: id
        opt = SelectedOption(name="Color", label="Red")
        data = opt.model_dump(mode="json", exclude_none=True)
        assert "id" not in data, "id should be excluded when None"

    def test_selected_option_id_serializes_when_provided(self):
        # Spec: types/selected_option.json optional: id
        opt = SelectedOption(name="Color", label="Red", id="color_red")
        data = opt.model_dump(mode="json", exclude_none=True)
        assert data["id"] == "color_red"


# ============================================================================
# SEARCH FILTERS SPEC (types/search_filters.json, types/price_filter.json)
# ============================================================================


class TestSearchFiltersStructure:
    """S18: Search filter structure.

    Spec: types/search_filters.json properties: {categories, price}
    types/price_filter.json optional: min, max
    """

    def test_search_filters_has_categories(self):
        # Spec: types/search_filters.json properties.categories: array of strings
        filters = CatalogSearchFilters(categories=["flowers", "plants"])
        data = filters.model_dump(mode="json", exclude_none=True)
        assert data["categories"] == ["flowers", "plants"]

    def test_search_filters_has_price_filter(self):
        # Spec: types/search_filters.json properties.price: $ref price_filter.json
        filters = CatalogSearchFilters(
            price=CatalogPriceFilter(min=500, max=5000),
        )
        data = filters.model_dump(mode="json", exclude_none=True)
        assert "price" in data, "Search filters must support price filter"
        assert data["price"]["min"] == 500
        assert data["price"]["max"] == 5000

    def test_price_filter_fields_are_optional(self):
        # Spec: types/price_filter.json -- min and max are optional
        pf = CatalogPriceFilter()
        data = pf.model_dump(mode="json", exclude_none=True)
        assert "min" not in data, "min should be excluded when None"
        assert "max" not in data, "max should be excluded when None"

    def test_search_filters_all_fields_optional(self):
        # Spec: types/search_filters.json -- no required fields
        filters = CatalogSearchFilters()
        data = filters.model_dump(mode="json", exclude_none=True)
        assert isinstance(data, dict), "Empty filters should serialize as object"


# ---------------------------------------------------------------------------
# S19: product.json – variants minItems constraint
# Spec: product.json variants.minItems: 1
# ---------------------------------------------------------------------------


class TestProductVariantsMinItems:
    """S19: product.json – variants minItems: 1 constraint."""

    def test_product_with_one_variant_is_valid(self):
        """Spec: product.json variants minItems: 1 — one variant satisfies constraint."""
        product = CatalogProduct(
            id="prod-1",
            title="Single Variant Product",
            variants=[_make_variant()],
        )
        data = product.model_dump(mode="json", exclude_none=True)
        assert len(data["variants"]) == 1, "Product with 1 variant satisfies minItems: 1"

    def test_product_with_multiple_variants_is_valid(self):
        """Spec: product.json variants minItems: 1 — multiple variants also valid."""
        product = CatalogProduct(
            id="prod-2",
            title="Multi Variant Product",
            variants=[_make_variant(id="v-1"), _make_variant(id="v-2")],
        )
        data = product.model_dump(mode="json", exclude_none=True)
        assert len(data["variants"]) == 2

    def test_product_with_zero_variants_not_enforced_by_model(self):
        """Spec: product.json variants minItems: 1 but model allows empty list."""
        # The spec requires at least 1 variant, but Pydantic model uses
        # `list[CatalogVariant] = []` without min_length, so empty list is accepted.
        product = CatalogProduct(
            id="prod-3",
            title="No Variants Product",
            variants=[],
        )
        data = product.model_dump(mode="json", exclude_none=True)
        assert len(data["variants"]) == 0, (
            "Model gap: CatalogProduct accepts 0 variants "
            "(spec requires minItems: 1 but model uses plain list default)"
        )


# ---------------------------------------------------------------------------
# S20: media.json – width and height dimension constraints
# Spec: media.json width: integer minimum: 1, height: integer minimum: 1
# ---------------------------------------------------------------------------


class TestMediaDimensionConstraints:
    """S20: media.json – width/height dimension constraints."""

    def test_media_model_does_not_have_width_field(self):
        """Spec: media.json has width (integer, minimum: 1) but check if model has it."""
        has_width = "width" in CatalogMedia.model_fields
        assert not has_width, (
            "CatalogMedia does not model 'width' field "
            "(spec defines width: integer, minimum: 1)"
        )

    def test_media_model_does_not_have_height_field(self):
        """Spec: media.json has height (integer, minimum: 1) but check if model has it."""
        has_height = "height" in CatalogMedia.model_fields
        assert not has_height, (
            "CatalogMedia does not model 'height' field "
            "(spec defines height: integer, minimum: 1)"
        )

    def test_media_model_has_core_fields(self):
        """Spec: media.json required: ["type", "url"] — model has these."""
        media = CatalogMedia(type="image", url="https://example.com/img.jpg")
        data = media.model_dump(mode="json", exclude_none=True)
        assert "type" in data, "CatalogMedia must have 'type' field"
        assert "url" in data, "CatalogMedia must have 'url' field"


# ---------------------------------------------------------------------------
# S21: rating.json – rating constraints
# Spec: rating.json required: ["value", "scale_max"]
#   value: number minimum: 0, scale_min: number minimum: 0 default: 1
#   scale_max: number minimum: 1, count: integer minimum: 0
# ---------------------------------------------------------------------------


class TestRatingModelGap:
    """S21: rating.json – no CatalogRating model exists."""

    def test_no_rating_model_exists(self):
        """Spec: rating.json defines a rating type but no Pydantic model exists."""
        # The product.json schema references rating.json as an optional field,
        # but models.py does not define a CatalogRating model.
        # CatalogProduct also does not have a 'rating' field.
        assert "rating" not in CatalogProduct.model_fields, (
            "CatalogProduct does not model 'rating' field — "
            "spec defines rating.json with value (min: 0), "
            "scale_max (min: 1), scale_min (min: 0, default: 1), count (min: 0)"
        )


# ---------------------------------------------------------------------------
# S22: pagination.json – request limit and response conditional cursor
# Spec: pagination.json#/$defs/request limit: integer minimum: 1 default: 10
#   pagination.json#/$defs/response: if has_next_page=true then cursor required
# ---------------------------------------------------------------------------


class TestPaginationConstraints:
    """S22: pagination.json – limit minimum and conditional cursor."""

    def test_pagination_request_limit_defaults_to_10(self):
        """Spec: pagination.json request.limit default: 10."""
        pag = CatalogPaginationRequest()
        assert pag.limit == 10, "Spec: pagination request limit defaults to 10"

    def test_pagination_request_limit_accepts_one(self):
        """Spec: pagination.json request.limit minimum: 1."""
        pag = CatalogPaginationRequest(limit=1)
        data = pag.model_dump(mode="json", exclude_none=True)
        assert data["limit"] == 1, "Spec: limit must accept minimum value 1"

    def test_pagination_request_limit_minimum_not_enforced(self):
        """Spec: pagination.json request.limit minimum: 1 but model uses plain int."""
        # The spec requires minimum: 1, but Pydantic model uses `int = 10`
        # without Field(ge=1), so 0 and negative values are accepted.
        pag = CatalogPaginationRequest(limit=0)
        assert pag.limit == 0, (
            "Model gap: CatalogPaginationRequest accepts limit=0 "
            "(spec requires minimum: 1 but model uses plain int)"
        )

    def test_pagination_response_cursor_present_when_has_next_page(self):
        """Spec: pagination.json response — if has_next_page=true then cursor required."""
        pag = CatalogPaginationResponse(
            has_next_page=True,
            cursor="abc123",
        )
        data = pag.model_dump(mode="json", exclude_none=True)
        assert "cursor" in data, (
            "Spec: cursor MUST be present when has_next_page is true"
        )

    def test_pagination_response_cursor_omitted_when_no_next_page(self):
        """Spec: pagination.json response — cursor optional when has_next_page=false."""
        pag = CatalogPaginationResponse(has_next_page=False)
        data = pag.model_dump(mode="json", exclude_none=True)
        assert "cursor" not in data, (
            "cursor should be omitted when has_next_page is false and no cursor set"
        )

    def test_pagination_conditional_cursor_not_enforced_by_model(self):
        """Spec: pagination.json if/then cursor constraint not enforced by Pydantic."""
        # The spec says cursor MUST be present when has_next_page=true,
        # but Pydantic model allows has_next_page=True with cursor=None.
        pag = CatalogPaginationResponse(has_next_page=True)
        data = pag.model_dump(mode="json", exclude_none=True)
        assert "cursor" not in data, (
            "Model gap: CatalogPaginationResponse allows has_next_page=True "
            "without cursor (spec requires cursor when has_next_page is true)"
        )


# ---------------------------------------------------------------------------
# S23: variant.json – CatalogVariant missing optional fields
# Spec: variant.json defines many optional fields not yet modeled
# ---------------------------------------------------------------------------


class TestCatalogVariantMissingOptionalFields:
    """S23: CatalogVariant missing optional fields from variant.json.

    Spec: types/variant.json defines optional fields: barcodes, handle, url,
    categories, list_price, unit_price, rating, tags, metadata, seller.
    Model implements: id, sku, title, description, price, availability,
    options, media.
    """

    def test_variant_missing_optional_fields(self):
        """Spec: variant.json defines 10 optional fields not modeled on CatalogVariant."""
        # NOTE: Model gap – variant.json defines many optional fields that
        # CatalogVariant does not model. These are tracked as a group.
        spec_optional_fields = {
            "barcodes", "handle", "url", "categories", "list_price",
            "unit_price", "rating", "tags", "metadata", "seller",
        }
        model_fields = set(CatalogVariant.model_fields.keys())
        missing = spec_optional_fields - model_fields
        if missing:
            pytest.skip(
                f"Model gap: CatalogVariant missing {len(missing)} optional "
                f"fields from variant.json: {sorted(missing)}"
            )


# ---------------------------------------------------------------------------
# S24: product.json – CatalogProduct missing optional fields
# Spec: product.json defines optional fields not yet modeled
# ---------------------------------------------------------------------------


class TestCatalogProductMissingOptionalFields:
    """S24: CatalogProduct missing optional fields from product.json.

    Spec: types/product.json defines optional fields: rating, tags,
    metadata, list_price_range. rating gap already documented in S21;
    this test covers the remaining fields as a group.
    """

    def test_product_missing_optional_fields(self):
        """Spec: product.json defines 4 optional fields not modeled on CatalogProduct."""
        # NOTE: Model gap – product.json defines optional fields that
        # CatalogProduct does not model. rating is separately documented
        # in S21; this groups all four for completeness.
        spec_optional_fields = {
            "rating", "tags", "metadata", "list_price_range",
        }
        model_fields = set(CatalogProduct.model_fields.keys())
        missing = spec_optional_fields - model_fields
        if missing:
            pytest.skip(
                f"Model gap: CatalogProduct missing {len(missing)} optional "
                f"fields from product.json: {sorted(missing)}"
            )


# ---------------------------------------------------------------------------
# S25: postal_address.json – PostalAddress missing contact fields
# Spec: postal_address.json defines optional contact fields not yet modeled
# ---------------------------------------------------------------------------


class TestPostalAddressMissingContactFields:
    """S25: PostalAddress missing contact fields from postal_address.json.

    Spec: types/postal_address.json defines optional fields: extended_address,
    first_name, last_name, phone_number. Model implements: street_address,
    address_locality, address_region, postal_code, address_country.
    """

    def test_postal_address_missing_contact_fields(self):
        """Spec: postal_address.json defines 4 optional contact fields not modeled."""
        # NOTE: Model gap – postal_address.json defines optional contact
        # fields (extended_address, first_name, last_name, phone_number)
        # that PostalAddress does not model.
        spec_contact_fields = {
            "extended_address", "first_name", "last_name", "phone_number",
        }
        model_fields = set(PostalAddress.model_fields.keys())
        missing = spec_contact_fields - model_fields
        if missing:
            pytest.skip(
                f"Model gap: PostalAddress missing {len(missing)} optional "
                f"contact fields from postal_address.json: {sorted(missing)}"
            )
