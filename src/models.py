"""Pydantic models for UCP checkout, order, and related types.

These replace the ucp_sdk dependency with lightweight inline models
that match the UCP schema for the Workers deployment.
"""

from __future__ import annotations
from pydantic import BaseModel
from typing import Any


# --- Internal response wrappers ---

class Version(str):
  pass


class ResponseCheckout(BaseModel):
  version: str
  capabilities: dict[str, list[dict[str, Any]]] = {}
  payment_handlers: dict[str, list[dict[str, Any]]] = {}


class ResponseOrder(BaseModel):
  version: str
  capabilities: dict[str, list[dict[str, Any]]] = {}


# --- Types ---

class PostalAddress(BaseModel):
  street_address: str | None = None
  address_locality: str | None = None
  address_region: str | None = None
  postal_code: str | None = None
  address_country: str | None = None


class ItemRequest(BaseModel):
  id: str
  title: str | None = None


class LineItemRequest(BaseModel):
  id: str | None = None
  item: ItemRequest
  quantity: int = 1
  parent_id: str | None = None


class ItemResponse(BaseModel):
  id: str
  title: str
  price: int = 0
  image_url: str | None = None


class TotalResponse(BaseModel):
  type: str
  display_text: str | None = None
  amount: int = 0


class LineItemResponse(BaseModel):
  id: str
  item: ItemResponse
  quantity: int = 1
  totals: list[TotalResponse] = []
  parent_id: str | None = None


class Buyer(BaseModel):
  first_name: str | None = None
  last_name: str | None = None
  full_name: str | None = None
  email: str | None = None
  phone_number: str | None = None
  consent: Any | None = None


# --- Payment ---

class PaymentInstrument(BaseModel):
  id: str
  handler_id: str
  type: str
  selected: bool | None = None
  billing_address: PostalAddress | None = None
  credential: Any | None = None
  display: dict[str, Any] | None = None


class PaymentResponse(BaseModel):
  instruments: list[PaymentInstrument] = []


# --- Fulfillment ---

class ShippingDestinationRequest(BaseModel):
  id: str | None = None
  address_country: str | None = None
  postal_code: str | None = None
  address_region: str | None = None
  address_locality: str | None = None
  street_address: str | None = None


class ShippingDestinationResponse(BaseModel):
  id: str | None = None
  address_country: str | None = None
  postal_code: str | None = None
  address_region: str | None = None
  address_locality: str | None = None
  street_address: str | None = None


class RetailLocation(BaseModel):
  id: str | None = None
  name: str
  address: PostalAddress | None = None


class FulfillmentOptionResponse(BaseModel):
  id: str
  title: str
  totals: list[TotalResponse] = []


class FulfillmentGroupResponse(BaseModel):
  id: str
  line_item_ids: list[str] | None = None
  selected_option_id: str | None = None
  options: list[FulfillmentOptionResponse] | None = None


class FulfillmentMethodRequest(BaseModel):
  id: str | None = None
  type: str = "shipping"
  line_item_ids: list[str] | None = None
  groups: list[FulfillmentGroupResponse] | None = None
  destinations: list[ShippingDestinationRequest | RetailLocation] | None = None
  selected_destination_id: str | None = None


class FulfillmentMethodResponse(BaseModel):
  id: str
  type: str = "shipping"
  line_item_ids: list[str] | None = None
  groups: list[FulfillmentGroupResponse] | None = None
  destinations: list[ShippingDestinationResponse | RetailLocation] | None = None
  selected_destination_id: str | None = None


class FulfillmentRequest(BaseModel):
  methods: list[FulfillmentMethodRequest] | None = None


class FulfillmentAvailableMethod(BaseModel):
  type: str
  line_item_ids: list[str]
  fulfillable_on: str | None = None
  description: str | None = None


class FulfillmentResponse(BaseModel):
  methods: list[FulfillmentMethodResponse] | None = None
  available_methods: list[FulfillmentAvailableMethod] | None = None


# --- Discount ---

class Allocation(BaseModel):
  path: str
  amount: int = 0


class AppliedDiscount(BaseModel):
  code: str | None = None
  title: str = ""
  amount: int = 0
  automatic: bool = False
  method: str | None = None
  priority: int | None = None
  allocations: list[Allocation] = []


class DiscountsObject(BaseModel):
  codes: list[str] | None = None
  applied: list[AppliedDiscount] | None = None


class DiscountsInput(BaseModel):
  codes: list[str] | None = None


# --- Order ---

class OrderQuantity(BaseModel):
  total: int = 0
  fulfilled: int = 0


class OrderLineItem(BaseModel):
  id: str
  item: ItemResponse
  quantity: OrderQuantity
  totals: list[TotalResponse] = []
  status: str = "processing"
  parent_id: str | None = None


class ExpectationLineItem(BaseModel):
  id: str
  quantity: int = 1


class Expectation(BaseModel):
  id: str
  line_items: list[ExpectationLineItem] = []
  method_type: str | None = None
  destination: PostalAddress | None = None
  description: str | None = None


class OrderFulfillment(BaseModel):
  expectations: list[Expectation] = []
  events: list[Any] = []


class OrderConfirmation(BaseModel):
  id: str
  permalink_url: str | None = None


class PlatformConfig(BaseModel):
  webhook_url: str | None = None


class Order(BaseModel):
  ucp: ResponseOrder | None = None
  id: str
  checkout_id: str | None = None
  permalink_url: str | None = None
  line_items: list[OrderLineItem] = []
  currency: str = "USD"
  totals: list[TotalResponse] = []
  fulfillment: OrderFulfillment | None = None


# --- Checkout ---

class CheckoutCreateRequest(BaseModel):
  cart_id: str | None = None
  line_items: list[LineItemRequest]
  buyer: Buyer | None = None
  context: Any | None = None
  payment: PaymentResponse | None = None
  fulfillment: FulfillmentRequest | None = None
  discounts: DiscountsInput | None = None
  signals: dict[str, Any] | None = None

  model_config = {"extra": "allow"}


class CheckoutUpdateRequest(BaseModel):
  line_items: list[LineItemRequest] | None = None
  buyer: Buyer | None = None
  context: Any | None = None
  payment: PaymentResponse | None = None
  fulfillment: FulfillmentRequest | None = None
  discounts: DiscountsInput | None = None
  signals: dict[str, Any] | None = None

  model_config = {"extra": "allow"}


class CheckoutCompleteRequest(BaseModel):
  payment: PaymentResponse
  signals: dict[str, Any] | None = None

  model_config = {"extra": "allow"}


class CheckoutLink(BaseModel):
  type: str
  url: str
  title: str | None = None


class CheckoutMessage(BaseModel):
  type: str = "info"
  code: str | None = None
  content: str | None = None


class Checkout(BaseModel):
  ucp: ResponseCheckout | None = None
  id: str
  line_items: list[LineItemResponse] = []
  buyer: Buyer | None = None
  context: Any | None = None
  status: str = "incomplete"
  currency: str = "USD"
  totals: list[TotalResponse] = []
  messages: list[CheckoutMessage] = []
  links: list[CheckoutLink] = []
  expires_at: str | None = None
  continue_url: str | None = None
  payment: PaymentResponse | None = None
  order: OrderConfirmation | None = None
  discounts: DiscountsObject | None = None
  fulfillment: FulfillmentResponse | None = None
  platform: PlatformConfig | None = None

  model_config = {"extra": "allow"}


# --- Catalog (2026-04-08) ---

class SelectedOption(BaseModel):
  name: str
  label: str
  id: str | None = None


class OptionValue(BaseModel):
  id: str | None = None
  label: str


class DetailOptionValue(BaseModel):
  id: str | None = None
  label: str
  available: bool | None = None
  exists: bool | None = None


class ProductOption(BaseModel):
  name: str
  values: list[OptionValue]


class DetailProductOption(BaseModel):
  name: str
  values: list[DetailOptionValue]


class CatalogPrice(BaseModel):
  amount: int = 0
  currency: str = "USD"


class CatalogPriceRange(BaseModel):
  min: CatalogPrice
  max: CatalogPrice


class CatalogMedia(BaseModel):
  type: str = "image"
  url: str
  alt_text: str | None = None


class CatalogCategory(BaseModel):
  value: str
  taxonomy: str = "merchant"


class CatalogAvailability(BaseModel):
  available: bool = True
  status: str = "in_stock"


class CatalogDescription(BaseModel):
  plain: str | None = None
  html: str | None = None


class CatalogVariant(BaseModel):
  id: str
  sku: str | None = None
  title: str | None = None
  description: CatalogDescription | None = None
  price: CatalogPrice | None = None
  availability: CatalogAvailability | None = None
  options: list[SelectedOption] = []
  media: list[CatalogMedia] = []


class CatalogProduct(BaseModel):
  id: str
  handle: str | None = None
  title: str
  description: CatalogDescription | None = None
  url: str | None = None
  price_range: CatalogPriceRange | None = None
  media: list[CatalogMedia] = []
  categories: list[CatalogCategory] = []
  variants: list[CatalogVariant] = []


class CatalogInputCorrelation(BaseModel):
  id: str
  match: str = "exact"


class CatalogVariantWithInputs(CatalogVariant):
  inputs: list[CatalogInputCorrelation] = []


class CatalogProductWithInputs(CatalogProduct):
  variants: list[CatalogVariantWithInputs] = []


class CatalogPaginationRequest(BaseModel):
  limit: int = 10
  cursor: str | None = None


class CatalogPaginationResponse(BaseModel):
  cursor: str | None = None
  has_next_page: bool = False
  total_count: int | None = None


class CatalogPriceFilter(BaseModel):
  min: int | None = None
  max: int | None = None


class CatalogSearchFilters(BaseModel):
  categories: list[str] | None = None
  price: CatalogPriceFilter | None = None


class CatalogContext(BaseModel):
  address_country: str | None = None
  language: str | None = None
  currency: str | None = None
  intent: str | None = None


class CatalogMessage(BaseModel):
  type: str = "info"
  code: str | None = None
  content: str | None = None


class CatalogUcp(BaseModel):
  version: str = "2026-04-08"
  capabilities: dict[str, list[dict[str, str]]] = {}
  # Per ucp.json#/$defs/base: "success" | "error", defaults to "success".
  status: str = "success"


class CatalogSearchRequest(BaseModel):
  query: str = ""
  filters: CatalogSearchFilters | None = None
  pagination: CatalogPaginationRequest | None = None
  context: CatalogContext | None = None
  signals: dict[str, Any] | None = None


class CatalogSearchResponse(BaseModel):
  ucp: CatalogUcp
  products: list[CatalogProduct] = []
  pagination: CatalogPaginationResponse


class CatalogLookupRequest(BaseModel):
  ids: list[str]
  filters: CatalogSearchFilters | None = None
  context: CatalogContext | None = None
  signals: dict[str, Any] | None = None


class CatalogLookupResponse(BaseModel):
  ucp: CatalogUcp
  products: list[CatalogProductWithInputs] = []
  messages: list[CatalogMessage] = []


class CatalogProductRequest(BaseModel):
  id: str
  selected: list[SelectedOption] | None = None
  preferences: list[str] | None = None
  context: CatalogContext | None = None
  signals: dict[str, Any] | None = None


class CatalogDetailProduct(CatalogProduct):
  """Product in a get_product response with effective selections and availability signals."""
  selected: list[SelectedOption] | None = None
  options: list[DetailProductOption] | None = None


class CatalogProductResponse(BaseModel):
  ucp: CatalogUcp
  product: CatalogDetailProduct | None = None
  messages: list[CatalogMessage] = []


# --- Cart (2026-04-08) ---

class ResponseCart(BaseModel):
  version: str
  capabilities: dict[str, list[dict[str, Any]]] = {}


class CartCreateRequest(BaseModel):
  line_items: list[LineItemRequest]
  buyer: Buyer | None = None
  context: Any | None = None
  signals: Any | None = None

  model_config = {"extra": "allow"}


class CartUpdateRequest(BaseModel):
  line_items: list[LineItemRequest] | None = None
  buyer: Buyer | None = None
  context: Any | None = None
  signals: Any | None = None

  model_config = {"extra": "allow"}


class CartLink(BaseModel):
  type: str
  url: str
  title: str | None = None


class Cart(BaseModel):
  ucp: ResponseCart | None = None
  id: str
  line_items: list[LineItemResponse] = []
  buyer: Buyer | None = None
  context: Any | None = None
  status: str = "active"
  currency: str = "USD"
  totals: list[TotalResponse] = []
  messages: list[CatalogMessage] = []
  links: list[CartLink] = []
  continue_url: str | None = None
  expires_at: str | None = None

  model_config = {"extra": "allow"}
