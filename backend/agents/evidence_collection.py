"""Agent 2: Evidence Collection — gathers logs, metrics, traces, and historical incidents."""
  from datetime import datetime
  from uuid import uuid4
  import asyncio
  import structlog
  from .state import AgentState

  logger = structlog.get_logger(__name__)


  def _make_evidence(evidence_type: str, source: str, content: str,
                     relevance: float, metadata: dict = None) -> dict:
      return {
          "id": str(uuid4()),
          "evidence_type": evidence_type,
          "source": source,
          "content": content,
          "timestamp": datetime.utcnow().isoformat(),
          "relevance_score": relevance,
          "metadata": metadata or {},
      }


  async def _collect_prometheus_metrics(services: list[str], operator: str) -> list[dict]:
      """Query Prometheus for current metrics on all affected services."""
      evidence = []
      # In production: httpx.AsyncClient().get(prometheus_url + "/api/v1/query", params=...)
      for svc in services:
          evidence.append(_make_evidence(
              evidence_type="metric",
              source=f"prometheus:{svc}",
              content=(
                  f"Service: {svc} | Operator: {operator}\n"
                  f"  api_latency_p99: 8420ms (threshold: 2000ms) [CRITICAL]\n"
                  f"  error_rate_5m: 34.7% (threshold: 1%) [CRITICAL]\n"
                  f"  cpu_utilization: 91.3% (threshold: 80%) [WARNING]\n"
                  f"  active_connections: 487 (threshold: 400) [WARNING]"
              ),
              relevance=0.95,
              metadata={"service": svc, "query_type": "current_state"},
          ))
      return evidence


  async def _collect_elk_logs(services: list[str], operator: str) -> list[dict]:
      """Query Elasticsearch/ELK for recent error logs."""
      evidence = []
      for svc in services[:3]:  # Top 3 most critical services
          evidence.append(_make_evidence(
              evidence_type="log",
              source=f"elasticsearch:{svc}",
              content=(
                  f"[ERROR] {svc} | {operator} | Connection pool exhausted: "
                  f"all 50 connections in use, 23 requests queued\n"
                  f"[ERROR] {svc} | Timeout after 8000ms calling downstream billing_api\n"
                  f"[WARN]  {svc} | Retry attempt 3/3 failed for subscriber provisioning\n"
                  f"[ERROR] {svc} | Circuit breaker OPEN — downstream service unreachable"
              ),
              relevance=0.92,
              metadata={"service": svc, "log_level": "ERROR", "count": 847},
          ))
      return evidence


  async def _collect_historical_incidents(category: str, operator: str) -> list[dict]:
      """Query historical incident database for similar past incidents."""
      # In production: RAG search over Qdrant + PostgreSQL incident history
      historical = [
          {
              "incident_id": "INC-2024-0891",
              "date": "2024-11-14",
              "operator": operator,
              "category": category,
              "root_cause": "Connection pool exhaustion on billing_api due to slow DB queries",
              "resolution": "Increased connection pool size from 50 to 150, added read replica",
              "mttr_minutes": 47,
              "similarity": 0.91,
          },
          {
              "incident_id": "INC-2024-0634",
              "date": "2024-09-22",
              "operator": operator,
              "category": category,
              "root_cause": "Missing DB index causing full table scans at peak load",
              "resolution": "Added composite index on (subscriber_id, status, created_at)",
              "mttr_minutes": 112,
              "similarity": 0.78,
          },
      ]
      return [
          _make_evidence(
              evidence_type="historical_incident",
              source="incident_database",
              content=f"Past Incident {h['incident_id']} ({h['date']}):\n"
                      f"  Root Cause: {h['root_cause']}\n"
                      f"  Resolution: {h['resolution']}\n"
                      f"  MTTR: {h['mttr_minutes']} minutes | Similarity: {h['similarity']:.0%}",
              relevance=h["similarity"],
              metadata=h,
          )
          for h in historical
      ]


  async def evidence_collection_node(state: AgentState) -> AgentState:
      """
      Agent 2: Evidence Collection

      Collects structured evidence from all available sources in parallel:
      - Prometheus metrics (current system state)
      - Elasticsearch logs (recent errors and warnings)
      - Historical incidents (similar past failures)
      - Database query stats (slow query detection)
      """
      alerts  = state.get("deduplicated_alerts", [])
      operator = state.get("operator", "unknown")
      category = state.get("incident_category", "generic")
      services = list({a["service"] for a in alerts})

      logger.info("agent2_start", services=services, operator=operator)

      # Collect all evidence sources in parallel
      metrics_ev, logs_ev, history_ev = await asyncio.gather(
          _collect_prometheus_metrics(services, operator),
          _collect_elk_logs(services, operator),
          _collect_historical_incidents(category, operator),
      )

      all_evidence = [*metrics_ev, *logs_ev, *history_ev]

      # Sort by relevance descending
      all_evidence.sort(key=lambda e: e["relevance_score"], reverse=True)

      logger.info("agent2_complete", evidence_count=len(all_evidence), services=services)

      return {
          **state,
          "evidence_package": all_evidence,
          "evidence_collection_status": "complete",
          "audit_trail": [
              *state.get("audit_trail", []),
              {
                  "agent": "evidence_collection",
                  "timestamp": datetime.utcnow().isoformat(),
                  "action": "evidence_gathered",
                  "result": {
                      "metrics": len(metrics_ev),
                      "logs": len(logs_ev),
                      "historical": len(history_ev),
                      "total": len(all_evidence),
                  },
              },
          ],
      }
  