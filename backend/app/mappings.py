from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MAPPINGS = ROOT / "mappings"
REGISTRY = MAPPINGS / "registry.json"


class MappingError(ValueError):
    pass


def _norm_project(value):
    normalized = re.sub(r"\s+", "", str(value or "")).upper()
    return normalized if re.fullmatch(r"P\d{6}", normalized) else None


def _norm_date(value):
    if not value:
        return None
    for fmt in ("%d-%b-%Y", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            return datetime.strptime(str(value).strip(), fmt).date().isoformat()
        except ValueError:
            pass
    return None


def _canonical_bytes(document: dict) -> bytes:
    return json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def mapping_hash(document: dict) -> str:
    return hashlib.sha256(_canonical_bytes(document)).hexdigest()


def load_registry() -> dict:
    return json.loads(REGISTRY.read_text(encoding="utf-8"))


def load_mapping(mapping_id: str, version: str | None = None) -> dict:
    registry = load_registry()
    entry = registry.get("mappings", {}).get(mapping_id)
    if not entry:
        raise MappingError(f"Unknown mapping: {mapping_id}")
    selected = version or entry["active"]
    relative_path = entry.get("versions", {}).get(selected)
    if not relative_path:
        raise MappingError(f"Unknown mapping version: {mapping_id}@{selected}")
    document = json.loads((MAPPINGS / relative_path).read_text(encoding="utf-8"))
    if document.get("mapping_id") != mapping_id or document.get("version") != selected:
        raise MappingError("Mapping identity does not match registry")
    document["sha256"] = mapping_hash(document)
    return document


def list_mappings() -> list[dict]:
    registry = load_registry()
    output = []
    for mapping_id, entry in registry["mappings"].items():
        active = load_mapping(mapping_id, entry["active"])
        output.append({
            "mapping_id": mapping_id,
            "active_version": entry["active"],
            "available_versions": sorted(entry["versions"]),
            "target": active["target"],
            "field_count": len(active["fields"]),
            "sha256": active["sha256"],
        })
    return output


def _source_value(path: str, record: dict, context: dict) -> Any:
    if path == "$record":
        return record
    if path.startswith("$computed."):
        return context.get("computed", {}).get(path.removeprefix("$computed."))
    if path.startswith("$constant."):
        return context.get("constants", {}).get(path.removeprefix("$constant."))
    value: Any = record
    for segment in path.split("."):
        value = value.get(segment) if isinstance(value, dict) else None
    return value


def _transform(name: str, value: Any) -> Any:
    transforms = {
        "identity": lambda v: v,
        "to_string": lambda v: None if v is None else str(v),
        "trim": lambda v: None if v is None else str(v).strip(),
        "uppercase": lambda v: None if v is None else str(v).strip().upper(),
        "normalize_project_id": _norm_project,
        "normalize_date": _norm_date,
        "join_list": lambda v: ", ".join(v) if isinstance(v, list) else (v or ""),
        "to_number": lambda v: None if v in (None, "") else float(v),
        "serialize_json": lambda v: json.dumps(v, ensure_ascii=False, sort_keys=True),
    }
    if name not in transforms:
        raise MappingError(f"Unsupported transform: {name}")
    return transforms[name](value)


def apply_mapping(mapping_id: str, record: dict, version: str | None = None, context: dict | None = None) -> dict:
    document = load_mapping(mapping_id, version)
    context = context or {}
    target, lineage = {}, []
    for field in document["fields"]:
        original = _source_value(field["source"], record, context)
        transformed = _transform(field.get("transform", "identity"), original)
        if field.get("required") and transformed in (None, ""):
            raise MappingError(f"Required target field is empty: {field['target']}")
        target[field["target"]] = transformed
        lineage.append({
            "source": field["source"],
            "target": field["target"],
            "transform": field.get("transform", "identity"),
        })
    return {
        "record": target,
        "lineage": lineage,
        "mapping_id": mapping_id,
        "mapping_version": document["version"],
        "mapping_hash": document["sha256"],
    }
