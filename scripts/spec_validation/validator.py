"""UCP spec validator core.

Builds a ``referencing.Registry`` from every JSON schema in ``spec/`` so that
``$ref`` pointers — whether absolute (``https://ucp.dev/schemas/...``) or
relative (``../ucp.json#/$defs/base``, ``types/line_item.json``) — resolve to
the pinned local copies rather than live network lookups.

The live UCP server may advertise a ``schema`` URL per capability, but agents
MUST validate against the schemas bundled with their understood spec version;
fetching live schemas would break pinning.

Exposes:
    load_registry() -> (registry, schema_index)
    resolve_schema_ref(ref, *, base_id=None) -> (resource, subschema)
    validate(instance, schema_ref) -> list[Error]
    Error is a tiny namedtuple of (path, message, schema_path)
"""
from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.exceptions import Unresolvable
from referencing.jsonschema import DRAFT202012

SPEC_ROOT = Path(__file__).parent / "spec"
SCHEMAS_ROOT = SPEC_ROOT / "source" / "schemas"
DISCOVERY_ROOT = SPEC_ROOT / "source" / "discovery"

# Canonical public IDs used by $ref in the spec. Map them to the local files.
ID_PREFIX = "https://ucp.dev/schemas/"
DISCOVERY_ID_PREFIX = "https://ucp.dev/schemas/discovery/"


@dataclass(frozen=True)
class Error:
    path: str        # JSON-pointer-like path into the instance
    message: str
    schema_path: str

    def __str__(self) -> str:
        return f"  at {self.path or '<root>'}: {self.message}"


def _walk_json(root: Path) -> Iterable[Path]:
    yield from root.rglob("*.json")


def _load_schema(path: Path) -> dict[str, Any]:
    with path.open("rb") as fh:
        return json.load(fh)


def load_registry() -> tuple[Registry, dict[str, dict[str, Any]]]:
    """Build a Registry that can resolve every $ref used in the spec.

    Returns (registry, index_by_id).  ``index_by_id`` maps each schema's $id
    to its parsed document, so callers can look up entrypoints directly.
    """
    resources: list[tuple[str, Resource]] = []
    index: dict[str, dict[str, Any]] = {}

    for file_path in list(_walk_json(SCHEMAS_ROOT)) + list(_walk_json(DISCOVERY_ROOT)):
        doc = _load_schema(file_path)
        schema_id = doc.get("$id")
        if not schema_id:
            continue

        # Fix: the discovery profile declares $id ".../schemas/discovery/profile.json"
        # but uses relative refs like "../schemas/ucp.json", which only resolve
        # if the base is ".../discovery/profile.json" (no "schemas/" prefix).
        # Rewrite in-memory so relative refs resolve the way the spec's build
        # pipeline intends.  The original $id is still registered below as an
        # alias so $ref to the canonical URL keeps working.
        original_id = schema_id
        if schema_id == "https://ucp.dev/schemas/discovery/profile.json":
            schema_id = "https://ucp.dev/discovery/profile.json"
            doc = {**doc, "$id": schema_id}

        resource = Resource(contents=doc, specification=DRAFT202012)
        resources.append((schema_id, resource))
        index[schema_id] = doc
        if original_id != schema_id:
            resources.append((original_id, resource))
            index[original_id] = doc

        # Register under every URL variant the server/spec might use:
        #  - canonical https://ucp.dev/schemas/shopping/foo.json
        #  - versioned https://ucp.dev/v2026-04-08/schemas/shopping/foo.json
        if schema_id.startswith(ID_PREFIX):
            tail = schema_id[len(ID_PREFIX):]
            resources.append(
                (f"https://ucp.dev/v2026-04-08/schemas/{tail}", resource),
            )

    registry = Registry().with_resources(resources)
    return registry, index


def resolve_schema_ref(
    ref: str,
    *,
    registry: Registry | None = None,
) -> dict[str, Any]:
    """Resolve a public schema $ref (with optional fragment) to its subschema.

    ``ref`` can be:
      - a canonical $id ("https://ucp.dev/schemas/shopping/cart.json")
      - a $id with fragment ("https://ucp.dev/schemas/shopping/catalog_search.json#/$defs/search_response")
    """
    if registry is None:
        registry, _ = load_registry()

    resolver = registry.resolver()
    resolved = resolver.lookup(ref)
    return resolved.contents


def validate(
    instance: Any,
    schema_ref: str,
    *,
    registry: Registry | None = None,
) -> list[Error]:
    """Validate ``instance`` against the schema at ``schema_ref``.

    The schema is wrapped in ``{"$ref": schema_ref}`` so that when callers pass
    a fragment like ``foo.json#/$defs/bar``, sibling ``$defs`` within foo.json
    remain reachable. Validating a fragment directly would strip that context.

    Returns a list of Error; empty list means valid.
    """
    if registry is None:
        registry, _ = load_registry()

    wrapper_schema = {"$ref": schema_ref}
    validator = Draft202012Validator(wrapper_schema, registry=registry)

    errors: list[Error] = []
    for err in sorted(validator.iter_errors(instance), key=lambda e: list(e.path)):
        path = "/" + "/".join(str(p) for p in err.absolute_path)
        schema_path = "/" + "/".join(str(p) for p in err.absolute_schema_path)
        errors.append(Error(path=path, message=err.message, schema_path=schema_path))
    return errors


__all__ = [
    "Error",
    "load_registry",
    "resolve_schema_ref",
    "validate",
    "Unresolvable",
]
