"""Discovery route for the UCP server."""

from fastapi import APIRouter, Request

router = APIRouter()

_SHOP_ID = None

def _get_shop_id():
  global _SHOP_ID
  if _SHOP_ID is None:
    import uuid
    _SHOP_ID = str(uuid.uuid4())
  return _SHOP_ID

DISCOVERY_PROFILE_TEMPLATE = {
  "ucp": {
    "version": "2026-04-08",
    "services": {
      "dev.ucp.shopping": [{
        "version": "2026-04-08",
        "transport": "rest",
        "spec": "https://ucp.dev/specification/reference",
        "schema": "https://ucp.dev/services/shopping/rest.openapi.json",
        "endpoint": "{{ENDPOINT}}"
      }]
    },
    "capabilities": {
      "dev.ucp.shopping.checkout": [{
        "version": "2026-04-08",
        "spec": "https://ucp.dev/specification/checkout",
        "schema": "https://ucp.dev/schemas/shopping/checkout.json"
      }],
      "dev.ucp.shopping.order": [{
        "version": "2026-04-08",
        "spec": "https://ucp.dev/specification/order",
        "schema": "https://ucp.dev/schemas/shopping/order.json"
      }],
      "dev.ucp.shopping.discount": [{
        "version": "2026-04-08",
        "spec": "https://ucp.dev/specification/discount",
        "schema": "https://ucp.dev/schemas/shopping/discount.json",
        "extends": "dev.ucp.shopping.checkout"
      }],
      "dev.ucp.shopping.fulfillment": [{
        "version": "2026-04-08",
        "spec": "https://ucp.dev/specification/fulfillment",
        "schema": "https://ucp.dev/schemas/shopping/fulfillment.json",
        "extends": "dev.ucp.shopping.checkout"
      }],
      "dev.ucp.shopping.buyer_consent": [{
        "version": "2026-04-08",
        "spec": "https://ucp.dev/specification/buyer-consent",
        "schema": "https://ucp.dev/schemas/shopping/buyer_consent.json",
        "extends": "dev.ucp.shopping.checkout"
      }],
      "dev.ucp.shopping.cart": [{
        "version": "2026-04-08",
        "spec": "https://ucp.dev/specification/cart",
        "schema": "https://ucp.dev/schemas/shopping/cart.json"
      }],
      "dev.ucp.shopping.catalog.search": [{
        "version": "2026-04-08",
        "spec": "https://ucp.dev/v2026-04-08/specification/catalog/search",
        "schema": "https://ucp.dev/v2026-04-08/schemas/shopping/catalog_search.json"
      }],
      "dev.ucp.shopping.catalog.lookup": [{
        "version": "2026-04-08",
        "spec": "https://ucp.dev/v2026-04-08/specification/catalog/lookup",
        "schema": "https://ucp.dev/v2026-04-08/schemas/shopping/catalog_lookup.json"
      }],
      "dev.ucp.shopping.catalog.product": [{
        "version": "2026-04-08",
        "spec": "https://ucp.dev/v2026-04-08/specification/catalog/product",
        "schema": "https://ucp.dev/v2026-04-08/schemas/shopping/catalog_product.json"
      }]
    },
    "payment_handlers": {
      "dev.shopify.shop_pay": [{
        "id": "shop_pay",
        "version": "2026-04-08",
        "spec": "https://shopify.dev/docs/agents/checkout/shop-pay-handler",
        "schema": "https://shopify.dev/ucp/shop-pay-handler/2026-01-11/config.json",
        "config": {
          "shop_id": "{{SHOP_ID}}"
        }
      }],
      "com.google.pay": [{
        "id": "google_pay",
        "version": "2026-04-08",
        "spec": "https://pay.google.com/gp/p/ucp/2026-01-11/",
        "schema": "https://pay.google.com/gp/p/ucp/2026-01-11/schemas/config.json",
        "config": {
          "api_version": 2,
          "api_version_minor": 0,
          "merchant_info": {
            "merchant_name": "Flower Shop",
            "merchant_id": "TEST",
            "merchant_origin": "localhost"
          },
          "allowed_payment_methods": [
            {
              "type": "CARD",
              "parameters": {
                "allowedAuthMethods": ["PAN_ONLY", "CRYPTOGRAM_3DS"],
                "allowedCardNetworks": ["VISA", "MASTERCARD"]
              },
              "tokenization_specification": [
                {
                  "type": "PAYMENT_GATEWAY",
                  "parameters": [
                    {
                      "gateway": "example",
                      "gatewayMerchantId": "exampleGatewayMerchantId"
                    }
                  ]
                }
              ]
            }
          ]
        }
      }]
    }
  }
}


def _build_profile(base_url):
  import copy
  import json
  profile = copy.deepcopy(DISCOVERY_PROFILE_TEMPLATE)
  endpoint = base_url.rstrip("/")

  # Replace placeholders via JSON round-trip
  profile_str = json.dumps(profile)
  profile_str = profile_str.replace("{{ENDPOINT}}", endpoint)
  profile_str = profile_str.replace("{{SHOP_ID}}", _get_shop_id())
  return json.loads(profile_str)


@router.get("/.well-known/ucp", summary="Get Merchant Profile")
async def get_merchant_profile(request: Request):
  return _build_profile(str(request.base_url))
