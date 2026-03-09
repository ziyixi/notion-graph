from __future__ import annotations

import hashlib
import hmac
from datetime import UTC, datetime
from typing import Any


def verify_webhook_signature(
    *,
    secret: str,
    body: bytes,
    signature_header: str | None,
    timestamp_header: str | None,
    max_age_seconds: int = 300,
) -> bool:
    if not secret:
        return True
    if not signature_header or not timestamp_header:
        return False
    if not _is_timestamp_fresh(timestamp_header, max_age_seconds=max_age_seconds):
        return False

    candidate_signatures = _extract_signature_candidates(signature_header)
    if not candidate_signatures:
        return False

    payload_text = body.decode("utf-8")
    signing_candidates = [
        f"{timestamp_header}.{payload_text}",
        f"{timestamp_header}:{payload_text}",
        payload_text,
    ]

    for signing_input in signing_candidates:
        expected = hmac.new(
            secret.encode("utf-8"),
            signing_input.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        for candidate in candidate_signatures:
            if hmac.compare_digest(expected, candidate):
                return True

    return False


def extract_page_ids_from_webhook(payload: dict[str, Any]) -> list[str]:
    page_ids: set[str] = set()

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            if "page_id" in node and isinstance(node["page_id"], str):
                page_ids.add(node["page_id"])
            if "pageId" in node and isinstance(node["pageId"], str):
                page_ids.add(node["pageId"])

            node_type = node.get("type")
            node_id = node.get("id")
            if node_type == "page" and isinstance(node_id, str):
                page_ids.add(node_id)

            page_obj = node.get("page")
            if isinstance(page_obj, dict):
                maybe_id = page_obj.get("id")
                if isinstance(maybe_id, str):
                    page_ids.add(maybe_id)

            entity = node.get("entity")
            if isinstance(entity, dict) and entity.get("type") == "page":
                entity_id = entity.get("id")
                if isinstance(entity_id, str):
                    page_ids.add(entity_id)

            for value in node.values():
                walk(value)
            return

        if isinstance(node, list):
            for item in node:
                walk(item)

    walk(payload)
    return sorted(page_ids)


def _extract_signature_candidates(signature_header: str) -> set[str]:
    signatures: set[str] = set()

    def normalize(token: str) -> str | None:
        trimmed = token.strip()
        if not trimmed:
            return None
        if "=" in trimmed:
            prefix, value = trimmed.split("=", 1)
            if prefix in {"v1", "sha256"}:
                trimmed = value.strip()
        if all(ch in "0123456789abcdefABCDEF" for ch in trimmed) and len(trimmed) >= 32:
            return trimmed.lower()
        return None

    for part in signature_header.split(","):
        candidate = normalize(part)
        if candidate:
            signatures.add(candidate)

    return signatures


def _is_timestamp_fresh(timestamp_header: str, max_age_seconds: int) -> bool:
    try:
        timestamp_int = int(timestamp_header)
    except ValueError:
        return False

    now = int(datetime.now(UTC).timestamp())
    return abs(now - timestamp_int) <= max_age_seconds
