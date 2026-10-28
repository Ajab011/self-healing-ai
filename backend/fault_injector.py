"""Generates fake broken workflow payloads for the demo.

Simulates an e-commerce "order sync" workflow (Shopify-style store -> CRM/fulfilment API)
breaking in one of three realistic ways. Each fault returns:
    {payload, error, fault_type, workflow, expected_schema}
`payload`, `error` and `fault_type` are the core contract; `workflow` and `expected_schema`
give the healer extra context to reason with.
"""

import random
import uuid
from datetime import datetime, timedelta, timezone

WORKFLOW = "order-sync: storefront webhook -> CRM /v2/orders"

EXPECTED_SCHEMA = {
    "order_id": "string",
    "customer_email": "string",
    "status": "string, one of: pending | shipped | delivered | cancelled",
    "total_price": "number (float, e.g. 49.99)",
    "currency": "string, ISO 4217 code",
    "created_at": "string, ISO 8601 datetime (e.g. 2026-10-28T14:30:00Z)",
}

_CUSTOMERS = ["priya.sharma@example.com", "rahul.verma@example.com", "ananya.k@example.com", "dev.patel@example.com"]
_STATUSES = ["pending", "shipped", "delivered"]


def _base_order() -> dict:
    created = datetime.now(timezone.utc) - timedelta(minutes=random.randint(1, 600))
    return {
        "order_id": f"ORD-{uuid.uuid4().hex[:8].upper()}",
        "customer_email": random.choice(_CUSTOMERS),
        "status": random.choice(_STATUSES),
        "total_price": round(random.uniform(199, 4999), 2),
        "currency": "INR",
        "created_at": created.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def _schema_drift() -> dict:
    """Upstream renamed `status` -> `delivery_status` without telling anyone."""
    order = _base_order()
    order["delivery_status"] = order.pop("status")
    return {
        "payload": order,
        "error": (
            "ValidationError: POST /v2/orders failed with 422 Unprocessable Entity. "
            "Missing required field 'status'. Unexpected field 'delivery_status'."
        ),
        "fault_type": "schema_drift",
    }


def _rate_limit() -> dict:
    """CRM API is throttling us; payload itself is fine."""
    retry_after = random.choice([5, 10, 30])
    return {
        "payload": _base_order(),
        "error": (
            "HTTPError 429 Too Many Requests: POST /v2/orders. "
            f"Response headers: Retry-After: {retry_after}, X-RateLimit-Remaining: 0, "
            "X-RateLimit-Limit: 100/min. Body: {\"error\": \"rate_limit_exceeded\"}"
        ),
        "fault_type": "rate_limit",
    }


def _malformed_data() -> dict:
    """Date arrives in a locale format and price arrives as a formatted string."""
    order = _base_order()
    created = datetime.strptime(order["created_at"], "%Y-%m-%dT%H:%M:%SZ")
    order["created_at"] = created.strftime("%d/%m/%Y %I:%M %p")
    order["total_price"] = f"₹{order['total_price']:,.2f}"
    return {
        "payload": order,
        "error": (
            "TypeError: field 'total_price' expected float, got str "
            f"('{order['total_price']}'). "
            f"ValueError: field 'created_at' does not match ISO 8601 ('{order['created_at']}')."
        ),
        "fault_type": "malformed_data",
    }


_FAULTS = [_schema_drift, _rate_limit, _malformed_data]


def get_random_fault() -> dict:
    fault = random.choice(_FAULTS)()
    fault["workflow"] = WORKFLOW
    fault["expected_schema"] = EXPECTED_SCHEMA
    return fault


if __name__ == "__main__":
    import json

    for make in _FAULTS:
        print(json.dumps(make(), indent=2, ensure_ascii=False))
        print("-" * 60)
