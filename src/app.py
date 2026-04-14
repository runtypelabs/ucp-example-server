"""FastAPI application for the UCP demo server."""

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from exceptions import UcpError
from routes.cart import router as cart_router
from routes.catalog import router as catalog_router
from routes.checkout import router as checkout_router
from routes.discovery import router as discovery_router
from routes.home import router as home_router
from routes.platform import router as platform_router

logging.basicConfig(level=logging.INFO)

app = FastAPI(
  title="UCP Shopping Service",
  version="2026-01-11",
  description="UCP Demo Server on Cloudflare Workers",
)


@app.exception_handler(UcpError)
async def ucp_exception_handler(request: Request, exc: UcpError):
  return JSONResponse(
    status_code=exc.status_code,
    content={"detail": exc.message, "code": exc.code},
  )


app.include_router(home_router)
app.include_router(cart_router)
app.include_router(catalog_router)
app.include_router(checkout_router)
app.include_router(discovery_router)
app.include_router(platform_router)
