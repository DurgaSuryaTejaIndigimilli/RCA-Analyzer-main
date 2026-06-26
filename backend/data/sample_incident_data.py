"""Synthetic incident dataset for RCA demo MVP."""
from core.log_chunker import log_chunker
from core.vector_store import vector_store


DEMO_INCIDENT = {
    "metadata": {
        "id": "INC-2026-0847",
        "title": "Payment Service Degradation — Checkout Failures",
        "severity": "P1",
        "status": "investigating",
        "started_at": "2026-06-26T02:14:00Z",
        "services": ["payment-api", "order-service", "postgres-primary", "redis-cache"],
        "platform": "incident",
    },
    "summary": {
        "deploy": "payment-api v2.4.1 deployed at 02:00 UTC (config change: db pool settings)",
        "impact": "42% checkout failure rate, $18K/min revenue impact, 847 failed transactions in 12 min",
        "hypothesis": "Database connection pool exhaustion after config deploy",
    },
    "timeline": [
        {
            "order": 1,
            "time": "2026-06-26T01:58:00Z",
            "title": "Config deploy started",
            "source": "deploy-bot",
            "details": "payment-api v2.4.1 — changed DATABASE_POOL_MAX from 50 to 10 in production ConfigMap",
        },
        {
            "order": 2,
            "time": "2026-06-26T02:00:00Z",
            "title": "Deploy completed",
            "source": "deploy-bot",
            "details": "Rolling restart finished across 6 payment-api pods in us-east-1",
        },
        {
            "order": 3,
            "time": "2026-06-26T02:14:00Z",
            "title": "Alarm: High checkout error rate",
            "source": "datadog",
            "details": "checkout.error_rate > 15% for 3 minutes (threshold: 5%)",
        },
        {
            "order": 4,
            "time": "2026-06-26T02:16:00Z",
            "title": "Alarm: DB connection pool saturated",
            "source": "prometheus",
            "details": "postgres.connection_pool_utilization > 95% on payment-db-primary",
        },
        {
            "order": 5,
            "time": "2026-06-26T02:18:00Z",
            "title": "PagerDuty incident opened",
            "source": "pagerduty",
            "details": "Escalated to payments on-call — Sev-1",
        },
    ],
    "alarms": [
        {
            "name": "CheckoutErrorRateHigh",
            "severity": "critical",
            "service": "payment-api",
            "fired_at": "2026-06-26T02:14:00Z",
            "status": "firing",
            "message": "Checkout error rate at 42% (baseline 0.8%)",
            "metric": "checkout.errors / checkout.attempts",
        },
        {
            "name": "DBConnectionPoolExhausted",
            "severity": "critical",
            "service": "postgres-primary",
            "fired_at": "2026-06-26T02:16:00Z",
            "status": "firing",
            "message": "All 10 connections in use, 234 requests waiting in queue",
            "metric": "pg.pool.active_connections / pg.pool.max_connections",
        },
        {
            "name": "PaymentLatencyP99",
            "severity": "warning",
            "service": "payment-api",
            "fired_at": "2026-06-26T02:15:00Z",
            "status": "firing",
            "message": "P99 latency 8.4s (SLO: 2s)",
            "metric": "http.request.duration.p99",
        },
        {
            "name": "OrderServiceTimeouts",
            "severity": "warning",
            "service": "order-service",
            "fired_at": "2026-06-26T02:17:00Z",
            "status": "firing",
            "message": "Upstream payment-api timeouts increased 12x",
            "metric": "upstream.timeout.count",
        },
    ],
    "logs": [
        {
            "service": "payment-api",
            "content": """2026-06-26T02:13:45Z INFO  [payment-api] Health check OK - pool active: 8/10
2026-06-26T02:14:02Z WARN  [payment-api] Slow query detected: charge_payment took 3200ms order_id=ord_8f2a
2026-06-26T02:14:08Z ERROR [payment-api] Failed to acquire DB connection within 5000ms - pool exhausted
2026-06-26T02:14:08Z ERROR [payment-api] charge_payment failed order_id=ord_8f2a: ConnectionPoolTimeout: timeout waiting for connection from pool
2026-06-26T02:14:09Z ERROR [payment-api] HTTP 503 POST /v1/charge - upstream database unavailable
2026-06-26T02:14:12Z ERROR [payment-api] Failed to acquire DB connection within 5000ms - pool exhausted
2026-06-26T02:14:15Z ERROR [payment-api] charge_payment failed order_id=ord_9b11: ConnectionPoolTimeout: timeout waiting for connection from pool
2026-06-26T02:14:18Z ERROR [payment-api] Connection leak suspected - 10/10 connections held > 30s
2026-06-26T02:14:18Z ERROR [payment-api] Stack trace:
    at Pool.acquire (db/pool.js:142)
    at chargePayment (services/payment.js:89)
    at processCheckout (handlers/checkout.js:34)
2026-06-26T02:14:22Z WARN  [payment-api] Circuit breaker HALF_OPEN for postgres-primary
2026-06-26T02:14:30Z ERROR [payment-api] Failed to acquire DB connection within 5000ms - pool exhausted
2026-06-26T02:14:35Z INFO  [payment-api] Config loaded: DATABASE_POOL_MAX=10 (previous: 50)""",
        },
        {
            "service": "order-service",
            "content": """2026-06-26T02:14:10Z INFO  [order-service] Processing checkout order_id=ord_8f2a
2026-06-26T02:14:15Z WARN  [order-service] payment-api call slow: 5200ms order_id=ord_8f2a
2026-06-26T02:14:16Z ERROR [order-service] payment-api returned 503 order_id=ord_8f2a
2026-06-26T02:14:16Z ERROR [order-service] Checkout failed: PaymentServiceUnavailable
2026-06-26T02:14:20Z ERROR [order-service] payment-api timeout after 10000ms order_id=ord_9b11
2026-06-26T02:14:21Z ERROR [order-service] Checkout failed: UpstreamTimeout payment-api
2026-06-26T02:14:25Z WARN  [order-service] Retry attempt 2/3 for order_id=ord_9c44
2026-06-26T02:14:30Z ERROR [order-service] All retries exhausted order_id=ord_9c44""",
        },
        {
            "service": "postgres-primary",
            "content": """2026-06-26T02:14:05Z LOG   connection received: host=10.0.4.12 user=payment_app
2026-06-26T02:14:06Z LOG   connection authorized: user=payment_app database=payments
2026-06-26T02:14:10Z WARN  too many connections for role "payment_app" (10/10 active)
2026-06-26T02:14:12Z ERROR FATAL: remaining connection slots are reserved for superuser
2026-06-26T02:14:14Z LOG   connection received: host=10.0.4.15 user=payment_app
2026-06-26T02:14:14Z ERROR FATAL: sorry, too many clients already
2026-06-26T02:14:18Z LOG   duration: 2847.231 ms  statement: SELECT * FROM charges WHERE order_id=$1 FOR UPDATE
2026-06-26T02:14:20Z WARN  long running transaction: pid=48291 duration=45s application=payment_app
2026-06-26T02:14:25Z LOG   checkpoint starting: time""",
        },
        {
            "service": "redis-cache",
            "content": """2026-06-26T02:13:50Z INFO  [redis-cache] Cache hit rate: 94.2%
2026-06-26T02:14:00Z INFO  [redis-cache] Evicted 12 keys due to maxmemory policy
2026-06-26T02:14:30Z WARN  [redis-cache] Increased cache misses on payment:session keys (+340%)
2026-06-26T02:14:35Z INFO  [redis-cache] No errors detected - service healthy""",
        },
    ],
    "past_incidents": [
        {
            "id": "INC-2025-1203",
            "title": "Payment DB Pool Exhaustion — Black Friday",
            "date": "2025-11-29",
            "tags": ["connection-pool", "payment-api", "postgres", "config-change"],
            "root_cause": "DATABASE_POOL_MAX set too low during traffic spike; connections not released due to missing finally block in chargePayment()",
            "resolution": "Increased pool to 50, fixed connection leak in payment.js, added pool utilization alert at 80%",
            "content": """## Incident Summary
On Black Friday 2025, checkout failures spiked to 38% when payment-api exhausted its DB connection pool.

## Timeline
- 14:00 — Traffic 3x normal
- 14:12 — DBConnectionPoolExhausted alarm fired
- 14:20 — Root cause identified: pool max=15 + connection leak in chargePayment

## Root Cause
Two contributing factors:
1. Pool size too small for peak load
2. Bug in payment.js: connection not released on validation error path (missing finally block)

## Fix
- Hotfix: pool max 15 → 50
- Code fix: PR #1847 add finally { conn.release() }
- Added alert: pg.pool.utilization > 80%

## Lessons Learned
- Never reduce pool size without load testing
- Connection leak tests required for all DB access paths""",
        },
        {
            "id": "INC-2025-0412",
            "title": "Redis Failover — Session Loss",
            "date": "2025-04-12",
            "tags": ["redis", "session", "failover"],
            "root_cause": "Redis primary failover during node upgrade caused transient session loss",
            "resolution": "Enabled Redis sentinel, increased session TTL buffer",
            "content": """Unrelated to current incident but affected checkout session continuity.
Redis was healthy during INC-2026-0847 per logs.""",
        },
    ],
}


async def load_demo_incident():
    """Index the synthetic incident and return metadata for the UI."""
    try:
        chunks = log_chunker.chunk_incident(DEMO_INCIDENT)
        if not chunks:
            return {"status": "error", "message": "No incident data to index"}

        vector_store.clear()
        vector_store.build_index(chunks)

        log_sources = len(DEMO_INCIDENT.get("logs", []))
        alarm_count = len(DEMO_INCIDENT.get("alarms", []))
        postmortem_count = len(DEMO_INCIDENT.get("past_incidents", []))

        chunk_types = {}
        for chunk in chunks:
            chunk_types[chunk.chunk_type] = chunk_types.get(chunk.chunk_type, 0) + 1

        return {
            "status": "success",
            "mode": "incident",
            "incident_info": {
                "name": DEMO_INCIDENT["metadata"]["id"],
                "title": DEMO_INCIDENT["metadata"]["title"],
                "description": DEMO_INCIDENT["summary"]["impact"],
                "severity": DEMO_INCIDENT["metadata"]["severity"],
                "status": DEMO_INCIDENT["metadata"]["status"],
                "started_at": DEMO_INCIDENT["metadata"]["started_at"],
                "services": DEMO_INCIDENT["metadata"]["services"],
                "platform": "incident",
            },
            "timeline": DEMO_INCIDENT["timeline"],
            "alarms": DEMO_INCIDENT["alarms"],
            "stats": {
                "log_sources": log_sources,
                "alarms": alarm_count,
                "past_incidents": postmortem_count,
                "total_chunks": len(chunks),
                "chunk_types": chunk_types,
                "total_lines": sum(
                    log.get("content", "").count("\n") + 1
                    for log in DEMO_INCIDENT.get("logs", [])
                ),
            },
        }
    except Exception as e:
        return {"status": "error", "message": f"Failed to load demo incident: {str(e)}"}
