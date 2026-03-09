import hashlib
import hmac
import json
from datetime import UTC, datetime

from app.notion.webhook import extract_page_ids_from_webhook, verify_webhook_signature


def test_extract_page_ids_from_webhook_nested_payload() -> None:
    payload = {
        "events": [
            {"entity": {"type": "page", "id": "page_a"}},
            {"page_id": "page_b"},
            {"nested": {"page": {"id": "page_c"}}},
        ]
    }

    assert extract_page_ids_from_webhook(payload) == ["page_a", "page_b", "page_c"]


def test_verify_webhook_signature_valid() -> None:
    secret = "top-secret"
    payload = {"entity": {"type": "page", "id": "page_123"}}
    body = json.dumps(payload).encode("utf-8")
    timestamp = str(int(datetime.now(UTC).timestamp()))

    signing_input = f"{timestamp}.{body.decode('utf-8')}"
    digest = hmac.new(
        secret.encode("utf-8"),
        signing_input.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    assert verify_webhook_signature(
        secret=secret,
        body=body,
        signature_header=f"v1={digest}",
        timestamp_header=timestamp,
    )


def test_verify_webhook_signature_invalid() -> None:
    timestamp = str(int(datetime.now(UTC).timestamp()))
    assert not verify_webhook_signature(
        secret="top-secret",
        body=b'{"hello":"world"}',
        signature_header="v1=deadbeef",
        timestamp_header=timestamp,
    )
