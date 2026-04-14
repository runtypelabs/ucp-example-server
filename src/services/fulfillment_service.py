"""Fulfillment service for calculating delivery options."""

import json
import db
from models import FulfillmentOptionResponse, RetailLocation, TotalResponse


# Demo retail locations for pickup
RETAIL_LOCATIONS = [
  RetailLocation(id="store_downtown", name="Downtown Flower Shop", address=None),
  RetailLocation(id="store_midtown", name="Midtown Garden Center", address=None),
  RetailLocation(id="store_uptown", name="Uptown Floral Studio", address=None),
]


class FulfillmentService:
  async def calculate_options(self, d1, address, promotions=None, subtotal=0, line_item_ids=None):
    """Calculate available fulfillment options based on the address."""
    if not address or not address.address_country:
      return []

    promotions = promotions or []
    line_item_ids = line_item_ids or []

    # Check for free shipping
    is_free_shipping = False
    for promo in promotions:
      if promo.type == "free_shipping":
        if promo.min_subtotal and subtotal >= promo.min_subtotal:
          is_free_shipping = True
          break
        eligible = promo.eligible_item_ids
        if eligible and isinstance(eligible, str):
          eligible = json.loads(eligible)
        if eligible and any(item_id in eligible for item_id in line_item_ids):
          is_free_shipping = True
          break

    db_rates = await db.get_shipping_rates(d1, address.address_country)

    # Deduplicate by service level, preferring specific country
    rates_by_level = {}
    for rate in db_rates:
      if rate.service_level not in rates_by_level:
        rates_by_level[rate.service_level] = rate
      else:
        existing = rates_by_level[rate.service_level]
        if existing.country_code == "default" and rate.country_code != "default":
          rates_by_level[rate.service_level] = rate

    sorted_rates = sorted(rates_by_level.values(), key=lambda r: r.price)
    options = []
    for rate in sorted_rates:
      price = rate.price
      title = rate.title

      if is_free_shipping and rate.service_level == "standard":
        price = 0
        title += " (Free)"

      options.append(
        FulfillmentOptionResponse(
          id=rate.id,
          title=title,
          totals=[
            TotalResponse(type="subtotal", amount=price),
            TotalResponse(type="total", amount=price),
          ],
        )
      )

    return options

  def calculate_pickup_options(self):
    """Calculate pickup fulfillment options (free in-store pickup)."""
    return [
      FulfillmentOptionResponse(
        id="pickup_standard",
        title="In-store pickup",
        totals=[
          TotalResponse(type="subtotal", amount=0),
          TotalResponse(type="total", amount=0),
        ],
      )
    ]

  def get_retail_locations(self):
    """Return available retail locations for pickup."""
    return RETAIL_LOCATIONS
