"""Minimal synchronous UCP HTTP client for validator scripts.

Uses urllib only so the validator has no heavy dependencies beyond
jsonschema/referencing. Adds the UCP agent/request headers every request
needs per the OpenAPI spec.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from typing import Any


AGENT_PROFILE = "https://agent.example/profile"


@dataclass(frozen=True)
class Response:
    status: int
    headers: dict[str, str]
    body: Any              # parsed JSON, or None if body was empty
    raw: bytes

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 300


class UcpClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    def _headers(
        self,
        *,
        idempotency_key: str | None = None,
        extra: dict[str, str] | None = None,
    ) -> dict[str, str]:
        h = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            # per rest.openapi.json components/parameters
            "UCP-Agent": f'profile="{AGENT_PROFILE}"',
            "User-Agent": "ucp-spec-validator/1.0 (+https://github.com/runtypelabs)",
            "Signature": "sig1=:stub:",
            "Signature-Input": 'sig1=();created=0;keyid="stub"',
            "Request-Id": f"req-{uuid.uuid4()}",
        }
        if idempotency_key:
            h["Idempotency-Key"] = idempotency_key
        if extra:
            h.update(extra)
        return h

    def request(
        self,
        method: str,
        path: str,
        *,
        body: Any = None,
        idempotency_key: str | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> Response:
        url = self.base_url + path
        data: bytes | None = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
        headers = self._headers(idempotency_key=idempotency_key, extra=extra_headers)
        req = urllib.request.Request(
            url,
            data=data,
            method=method.upper(),
            headers=headers,
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read()
                status = resp.status
                response_headers = {k: v for k, v in resp.headers.items()}
        except urllib.error.HTTPError as http_err:
            raw = http_err.read() or b""
            status = http_err.code
            response_headers = {k: v for k, v in http_err.headers.items()}

        parsed: Any = None
        if raw.strip():
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                parsed = None

        return Response(
            status=status, headers=response_headers, body=parsed, raw=raw,
        )

    def get(self, path: str, **kw: Any) -> Response:
        return self.request("GET", path, **kw)

    def post(self, path: str, body: Any = None, **kw: Any) -> Response:
        return self.request("POST", path, body=body, **kw)

    def put(self, path: str, body: Any = None, **kw: Any) -> Response:
        return self.request("PUT", path, body=body, **kw)


def new_idempotency_key() -> str:
    return f"idem-{int(time.time())}-{uuid.uuid4().hex[:8]}"
