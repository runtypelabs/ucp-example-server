"""Cloudflare Workers entry point.

`from app import app` and `WorkerEntrypoint` are at module scope so the
Workers runtime captures FastAPI, Pydantic, httpx, and our route/service
graph in the deploy-time dedicated memory snapshot (see
`python_dedicated_snapshot` in wrangler.toml). This is what keeps cold
starts fast.

`asgi` is imported lazily inside `fetch` because it holds references to
JavaScript functions from the Workers runtime, which cannot be serialized
into the snapshot.

See: https://developers.cloudflare.com/workers/languages/python/how-python-workers-work/
"""

from workers import WorkerEntrypoint

from app import app


class Default(WorkerEntrypoint):
  async def fetch(self, request):
    import asgi
    app.state.db = self.env.DB
    app.state.runtype_client_token = getattr(self.env, "RUNTYPE_CLIENT_TOKEN", None)
    return await asgi.fetch(app, request, self.env)
