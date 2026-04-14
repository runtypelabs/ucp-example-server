"""Cloudflare Workers entry point — lazy-loads FastAPI to stay under startup CPU limit."""

_app = None


def _get_app():
  global _app
  if _app is None:
    from app import app
    _app = app
  return _app


async def on_fetch(request, env):
  import asgi
  app = _get_app()
  app.state.db = env.DB
  app.state.runtype_client_token = getattr(env, "RUNTYPE_CLIENT_TOKEN", None)
  return await asgi.fetch(app, request, env)
