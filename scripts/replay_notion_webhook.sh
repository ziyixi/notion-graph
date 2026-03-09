#!/usr/bin/env bash

set -euo pipefail

URL="http://localhost:8000/api/webhooks/notion"
SECRET=""
PAGE_ID="alice_page"
PAYLOAD_FILE=""
SHOW_PAYLOAD="false"

usage() {
  cat <<'EOF'
Replay a signed Notion webhook payload to the local backend.

Usage:
  replay_notion_webhook.sh [options]

Options:
  --url <url>                 Webhook endpoint URL (default: http://localhost:8000/api/webhooks/notion)
  --secret <secret>           HMAC secret used for signature generation (required)
  --page-id <id>              Page ID used in generated payload (default: alice_page)
  --payload-file <path>       Optional JSON payload file. If set, page-id is ignored.
  --show-payload              Print payload before sending.
  -h, --help                  Show this help message.

Signature format:
  x-notion-signature: v1=<hex_hmac_sha256(timestamp.payload)>
  x-notion-request-timestamp: <unix_timestamp_seconds>
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --url)
      URL="${2:-}"
      shift 2
      ;;
    --secret)
      SECRET="${2:-}"
      shift 2
      ;;
    --page-id)
      PAGE_ID="${2:-}"
      shift 2
      ;;
    --payload-file)
      PAYLOAD_FILE="${2:-}"
      shift 2
      ;;
    --show-payload)
      SHOW_PAYLOAD="true"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ -z "$SECRET" ]]; then
  echo "Error: --secret is required" >&2
  exit 1
fi

if [[ -n "$PAYLOAD_FILE" ]]; then
  if [[ ! -f "$PAYLOAD_FILE" ]]; then
    echo "Error: payload file not found: $PAYLOAD_FILE" >&2
    exit 1
  fi
  PAYLOAD="$(cat "$PAYLOAD_FILE")"
else
  PAYLOAD=$(printf '{"events":[{"entity":{"type":"page","id":"%s"}}]}' "$PAGE_ID")
fi

TIMESTAMP="$(date +%s)"
SIGNATURE="$(
  printf "%s.%s" "$TIMESTAMP" "$PAYLOAD" \
    | openssl dgst -sha256 -hmac "$SECRET" -binary \
    | xxd -p -c 256
)"

if [[ "$SHOW_PAYLOAD" == "true" ]]; then
  echo "Payload:"
  echo "$PAYLOAD"
fi

echo "POST $URL"
echo "Headers:"
echo "  x-notion-request-timestamp: $TIMESTAMP"
echo "  x-notion-signature: v1=$SIGNATURE"
echo

curl --silent --show-error --location "$URL" \
  --request POST \
  --header "Content-Type: application/json" \
  --header "x-notion-request-timestamp: $TIMESTAMP" \
  --header "x-notion-signature: v1=$SIGNATURE" \
  --data "$PAYLOAD"

echo
