"""Catalog routes for the UCP server (2026-04-08)."""

import json
import logging

from fastapi import APIRouter, Body, Header, Request

import db
from models import (
  CatalogAvailability,
  CatalogCategory,
  CatalogDescription,
  CatalogDetailProduct,
  CatalogInputCorrelation,
  CatalogLookupRequest,
  CatalogLookupResponse,
  CatalogMedia,
  CatalogMessage,
  CatalogPaginationResponse,
  CatalogPrice,
  CatalogPriceRange,
  CatalogProduct,
  CatalogProductRequest,
  CatalogProductResponse,
  CatalogProductWithInputs,
  CatalogSearchRequest,
  CatalogSearchResponse,
  CatalogUcp,
  CatalogVariant,
  CatalogVariantWithInputs,
  DetailOptionValue,
  DetailProductOption,
  SelectedOption,
)

logger = logging.getLogger(__name__)

router = APIRouter()

VERSION = "2026-04-08"


def _make_ucp(capability):
  return CatalogUcp(
    version=VERSION,
    capabilities={capability: [{"version": VERSION}]},
  )


def _row_to_product(row, base_url=""):
  """Convert a D1 row to a CatalogProduct."""
  price = CatalogPrice(amount=row.price, currency=getattr(row, "currency", "USD") or "USD")
  media = []
  if row.image_url:
    media.append(CatalogMedia(type="image", url=row.image_url, alt_text=row.title))

  categories = []
  raw_cats = getattr(row, "categories", "[]") or "[]"
  try:
    for cat in json.loads(raw_cats):
      categories.append(CatalogCategory(**cat))
  except (json.JSONDecodeError, TypeError):
    pass

  stock = getattr(row, "stock", 0) or 0
  avail = CatalogAvailability(
    available=stock > 0,
    status="in_stock" if stock > 0 else "out_of_stock",
  )

  desc_text = getattr(row, "description", "") or ""
  handle = getattr(row, "handle", "") or ""
  product_url = f"{base_url}/catalog/product" if base_url else None

  variant = CatalogVariant(
    id=row.id,
    title=row.title,
    description=CatalogDescription(plain=desc_text) if desc_text else CatalogDescription(plain=row.title),
    price=price,
    availability=avail,
    media=media,
  )

  return CatalogProduct(
    id=row.id,
    handle=handle,
    title=row.title,
    description=CatalogDescription(plain=desc_text) if desc_text else None,
    url=product_url,
    price_range=CatalogPriceRange(min=price, max=price),
    media=media,
    categories=categories,
    variants=[variant],
  )


def _row_to_product_with_inputs(row, input_id, base_url=""):
  """Convert a D1 row to a CatalogProductWithInputs for lookup."""
  price = CatalogPrice(amount=row.price, currency=getattr(row, "currency", "USD") or "USD")
  media = []
  if row.image_url:
    media.append(CatalogMedia(type="image", url=row.image_url, alt_text=row.title))

  categories = []
  raw_cats = getattr(row, "categories", "[]") or "[]"
  try:
    for cat in json.loads(raw_cats):
      categories.append(CatalogCategory(**cat))
  except (json.JSONDecodeError, TypeError):
    pass

  stock = getattr(row, "stock", 0) or 0
  avail = CatalogAvailability(
    available=stock > 0,
    status="in_stock" if stock > 0 else "out_of_stock",
  )

  desc_text = getattr(row, "description", "") or ""
  handle = getattr(row, "handle", "") or ""

  variant = CatalogVariantWithInputs(
    id=row.id,
    title=row.title,
    price=price,
    availability=avail,
    media=media,
    inputs=[CatalogInputCorrelation(id=input_id, match="exact")],
  )

  return CatalogProductWithInputs(
    id=row.id,
    handle=handle,
    title=row.title,
    description=CatalogDescription(plain=desc_text) if desc_text else None,
    price_range=CatalogPriceRange(min=price, max=price),
    media=media,
    categories=categories,
    variants=[variant],
  )


@router.post("/catalog/search")
async def catalog_search(
  request: Request,
  body: CatalogSearchRequest = Body(...),
  ucp_agent: str = Header(...),
  signature: str = Header(..., alias="Signature"),
  request_id: str = Header(...),
  signature_input: str | None = Header(None, alias="Signature-Input"),
  content_digest: str | None = Header(None, alias="Content-Digest"),
  authorization: str | None = Header(None, alias="Authorization"),
  x_api_key: str | None = Header(None, alias="X-API-Key"),
):
  d1 = request.app.state.db
  base_url = str(request.base_url).rstrip("/")

  limit = 10
  offset = 0
  if body.pagination:
    limit = min(body.pagination.limit or 10, 50)
    if body.pagination.cursor:
      try:
        offset = int(body.pagination.cursor)
      except ValueError:
        offset = 0

  price_min = None
  price_max = None
  if body.filters and body.filters.price:
    price_min = body.filters.price.min
    price_max = body.filters.price.max

  rows, total = await db.search_products(
    d1, query=body.query, price_min=price_min, price_max=price_max,
    limit=limit, offset=offset,
  )

  products = [_row_to_product(row, base_url) for row in rows]
  has_next = (offset + limit) < total
  next_cursor = str(offset + limit) if has_next else None

  return CatalogSearchResponse(
    ucp=_make_ucp("dev.ucp.shopping.catalog.search"),
    products=products,
    pagination=CatalogPaginationResponse(
      cursor=next_cursor,
      has_next_page=has_next,
      total_count=total,
    ),
  ).model_dump(mode="json")


@router.post("/catalog/lookup")
async def catalog_lookup(
  request: Request,
  body: CatalogLookupRequest = Body(...),
  ucp_agent: str = Header(...),
  signature: str = Header(..., alias="Signature"),
  request_id: str = Header(...),
  signature_input: str | None = Header(None, alias="Signature-Input"),
  content_digest: str | None = Header(None, alias="Content-Digest"),
  authorization: str | None = Header(None, alias="Authorization"),
  x_api_key: str | None = Header(None, alias="X-API-Key"),
):
  d1 = request.app.state.db

  if len(body.ids) > 50:
    from fastapi import HTTPException
    raise HTTPException(status_code=400, detail={
      "code": "request_too_large",
      "message": "Maximum 50 IDs per lookup request",
    })

  rows = await db.lookup_products(d1, body.ids)

  found_ids = {row.id for row in rows}
  products = []
  for row in rows:
    # Find the input ID that matched this row
    input_id = row.id  # direct match
    for req_id in body.ids:
      if req_id == row.id:
        input_id = req_id
        break
    products.append(_row_to_product_with_inputs(row, input_id))

  messages = []
  for req_id in body.ids:
    if req_id not in found_ids:
      messages.append(CatalogMessage(
        type="info", code="not_found",
        content=f"Product '{req_id}' was not found",
      ))

  return CatalogLookupResponse(
    ucp=_make_ucp("dev.ucp.shopping.catalog.lookup"),
    products=products,
    messages=messages,
  ).model_dump(mode="json")


def _resolve_product_detail(product_row, variants_data, options_data, selected, preferences, base_url=""):
  """Build a detail_product response with interactive option selection.

  Algorithm:
  1. If selected options are given, find the best-matching variant
  2. Use preferences for relaxation priority (drop from end first)
  3. Build option values with available/exists signals
  """
  # Parse variant options from JSON
  parsed_variants = []
  for v in variants_data:
    v_options = json.loads(v.options) if isinstance(v.options, str) else v.options
    parsed_variants.append({
      "id": v.id,
      "title": v.title,
      "sku": v.sku,
      "price": v.price,
      "available": bool(v.available),
      "options": [SelectedOption(**o) for o in v_options],
    })

  # Build product option structure from DB rows
  options_by_name = {}
  for row in options_data:
    if row.name not in options_by_name:
      options_by_name[row.name] = []
    options_by_name[row.name].append({"id": row.value_id, "label": row.label})

  # Determine effective selection
  effective_selected = selected or []

  # Find best matching variant with relaxation
  featured_variant = _find_best_variant(parsed_variants, effective_selected, preferences or [])

  # If a variant was found, use its options as effective selected
  if featured_variant:
    effective_selected = featured_variant["options"]

  # Build detail options with availability signals
  detail_options = []
  for opt_name, opt_values in options_by_name.items():
    detail_values = []
    for val in opt_values:
      # Compute exists/available relative to current selections (excluding this option axis)
      other_selections = [s for s in effective_selected if s.name != opt_name]
      exists = _variant_exists_with(parsed_variants, opt_name, val["label"], other_selections)
      available = _variant_available_with(parsed_variants, opt_name, val["label"], other_selections)
      detail_values.append(DetailOptionValue(
        id=val["id"], label=val["label"], available=available, exists=exists,
      ))
    detail_options.append(DetailProductOption(name=opt_name, values=detail_values))

  # Build the product base from the row
  price = CatalogPrice(amount=product_row.price, currency=getattr(product_row, "currency", "USD") or "USD")
  media = []
  if product_row.image_url:
    media.append(CatalogMedia(type="image", url=product_row.image_url, alt_text=product_row.title))

  categories = []
  raw_cats = getattr(product_row, "categories", "[]") or "[]"
  try:
    for cat in json.loads(raw_cats):
      categories.append(CatalogCategory(**cat))
  except (json.JSONDecodeError, TypeError):
    pass

  desc_text = getattr(product_row, "description", "") or ""
  handle = getattr(product_row, "handle", "") or ""

  # Build variants for response (all variants with their options)
  response_variants = []
  for pv in parsed_variants:
    avail = CatalogAvailability(
      available=pv["available"],
      status="in_stock" if pv["available"] else "out_of_stock",
    )
    response_variants.append(CatalogVariant(
      id=pv["id"], sku=pv["sku"], title=pv["title"],
      price=CatalogPrice(amount=pv["price"], currency=getattr(product_row, "currency", "USD") or "USD"),
      availability=avail,
      options=pv["options"],
    ))

  # Featured variant first
  if featured_variant:
    response_variants.sort(key=lambda v: v.id != featured_variant["id"])

  # Compute price range from variants
  if parsed_variants:
    min_price = min(v["price"] for v in parsed_variants)
    max_price = max(v["price"] for v in parsed_variants)
    currency = getattr(product_row, "currency", "USD") or "USD"
    price_range = CatalogPriceRange(
      min=CatalogPrice(amount=min_price, currency=currency),
      max=CatalogPrice(amount=max_price, currency=currency),
    )
  else:
    price_range = CatalogPriceRange(min=price, max=price)

  return CatalogDetailProduct(
    id=product_row.id,
    handle=handle,
    title=product_row.title,
    description=CatalogDescription(plain=desc_text) if desc_text else None,
    url=f"{base_url}/catalog/product" if base_url else None,
    price_range=price_range,
    media=media,
    categories=categories,
    variants=response_variants,
    selected=effective_selected if effective_selected else None,
    options=detail_options if detail_options else None,
  )


def _find_best_variant(variants, selected, preferences):
  """Find best matching variant, relaxing from end of preferences if no exact match."""
  if not selected:
    # No selection - return first available variant
    for v in variants:
      if v["available"]:
        return v
    return variants[0] if variants else None

  # Try exact match first
  match = _match_variant(variants, selected)
  if match:
    return match

  # Relax from end of preferences
  selections_to_try = list(selected)
  prefs_reversed = list(reversed(preferences)) if preferences else []

  for pref_name in prefs_reversed:
    selections_to_try = [s for s in selections_to_try if s.name != pref_name]
    if not selections_to_try:
      break
    match = _match_variant(variants, selections_to_try)
    if match:
      return match

  # Last resort - return first available
  for v in variants:
    if v["available"]:
      return v
  return variants[0] if variants else None


def _match_variant(variants, selected):
  """Find a variant matching all selected options. Prefer available ones."""
  matches = []
  for v in variants:
    v_opts = {o.name: o.label for o in v["options"]}
    if all(v_opts.get(s.name) == s.label for s in selected):
      matches.append(v)

  # Prefer available
  for m in matches:
    if m["available"]:
      return m
  return matches[0] if matches else None


def _variant_exists_with(variants, opt_name, opt_label, other_selections):
  """Check if any variant exists with this option value and other selections."""
  for v in variants:
    v_opts = {o.name: o.label for o in v["options"]}
    if v_opts.get(opt_name) != opt_label:
      continue
    if all(v_opts.get(s.name) == s.label for s in other_selections):
      return True
  return False


def _variant_available_with(variants, opt_name, opt_label, other_selections):
  """Check if an available variant exists with this option value and other selections."""
  for v in variants:
    if not v["available"]:
      continue
    v_opts = {o.name: o.label for o in v["options"]}
    if v_opts.get(opt_name) != opt_label:
      continue
    if all(v_opts.get(s.name) == s.label for s in other_selections):
      return True
  return False


@router.post("/catalog/product")
async def catalog_product(
  request: Request,
  body: CatalogProductRequest = Body(...),
  ucp_agent: str = Header(...),
  signature: str = Header(..., alias="Signature"),
  request_id: str = Header(...),
  signature_input: str | None = Header(None, alias="Signature-Input"),
  content_digest: str | None = Header(None, alias="Content-Digest"),
  authorization: str | None = Header(None, alias="Authorization"),
  x_api_key: str | None = Header(None, alias="X-API-Key"),
):
  d1 = request.app.state.db
  base_url = str(request.base_url).rstrip("/")

  # Check if ID matches a variant first
  variant_row = await db.get_variant_by_id(d1, body.id)
  if variant_row:
    product_id = variant_row.product_id
    # When a variant ID is provided, its options become the effective selection
    v_options = json.loads(variant_row.options) if isinstance(variant_row.options, str) else variant_row.options
    body.selected = [SelectedOption(**o) for o in v_options]
  else:
    product_id = body.id

  row = await db.get_product_detail(d1, product_id)
  if not row:
    return CatalogProductResponse(
      ucp=CatalogUcp(
        version=VERSION,
        capabilities={"dev.ucp.shopping.catalog.product": [{"version": VERSION}]},
        status="error",
      ),
      product=None,
      messages=[CatalogMessage(
        type="error", code="not_found",
        content=f"Product '{body.id}' was not found",
      )],
    ).model_dump(mode="json")

  # Load product options and variants from DB
  options_data = await db.get_product_options(d1, product_id)
  variants_data = await db.get_product_variants(d1, product_id)

  if variants_data:
    # Product has configurable options - use detail_product response
    product = _resolve_product_detail(row, variants_data, options_data, body.selected, body.preferences, base_url)
  else:
    # Simple product (no variants table entries) - return as basic detail_product
    base_product = _row_to_product(row, base_url)
    product = CatalogDetailProduct(
      id=base_product.id, handle=base_product.handle, title=base_product.title,
      description=base_product.description, url=base_product.url,
      price_range=base_product.price_range, media=base_product.media,
      categories=base_product.categories, variants=base_product.variants,
    )

  return CatalogProductResponse(
    ucp=_make_ucp("dev.ucp.shopping.catalog.product"),
    product=product,
  ).model_dump(mode="json")
