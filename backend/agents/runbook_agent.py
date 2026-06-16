"""Agent 4: Runbook Agent — maps incidents to SOPs via vector similarity."""
  from datetime import datetime
  import structlog
  from .state import AgentState

  logger = structlog.get_logger(__name__)

  # Runbook knowledge base for CRBT/VAS platforms
  # In production: stored in Qdrant and retrieved via vector similarity search
  RUNBOOKS: dict[str, dict] = {
      "database_bottleneck": {
          "title": "DB Connection Pool Exhaustion — CRBT/VAS Recovery",
          "steps": [
              {
                  "step_number": 1,
                  "title": "Verify Current Connection Pool Status",
                  "description": "Check live connection count vs pool limit on db_primary.",
                  "command": "SELECT count(*), state FROM pg_stat_activity GROUP BY state;",
                  "action_type": "read_only",
                  "expected_outcome": "Confirm pool saturation. Expect >45 active connections.",
              },
              {
                  "step_number": 2,
                  "title": "Identify Slow Queries Holding Connections",
                  "description": "Find queries running longer than 5 seconds.",
                  "command": "SELECT pid, now()-query_start AS duration, query FROM pg_stat_activity WHERE state='active' AND now()-query_start > interval '5 seconds' ORDER BY duration DESC;",
                  "action_type": "read_only",
                  "expected_outcome": "Identify blocking query PIDs and SQL statements.",
              },
              {
                  "step_number": 3,
                  "title": "Check CRBT Activation Error Rate",
                  "description": "Verify activation success rate in Prometheus.",
                  "command": "rate(crbt_activation_success_total[5m]) / rate(crbt_activation_attempts_total[5m])",
                  "action_type": "read_only",
                  "expected_outcome": "Confirm activation success rate < 30% (critical threshold).",
              },
              {
                  "step_number": 4,
                  "title": "Increase Connection Pool Size (REQUIRES APPROVAL)",
                  "description": "Submit request to increase PgBouncer pool_size from 50 to 150. This is a configuration change requiring L2 approval.",
                  "command": "pgbouncer_reload_config --pool-size=150  # Requires approval before execution",
                  "action_type": "assisted",
                  "expected_outcome": "Connection wait queue clears within 2 minutes.",
              },
              {
                  "step_number": 5,
                  "title": "Monitor Recovery",
                  "description": "Watch activation success rate and API latency for 10 minutes post-change.",
                  "command": None,
                  "action_type": "read_only",
                  "expected_outcome": "Activation success rate returns to >95% within 10 minutes.",
              },
          ],
      },
      "billing_timeout": {
          "title": "Billing API Timeout — VAS Recovery Procedure",
          "steps": [
              {
                  "step_number": 1,
                  "title": "Confirm Billing API Health",
                  "description": "Check health endpoint and current latency metrics.",
                  "command": "curl -s http://billing-api:8080/actuator/health | jq .",
                  "action_type": "read_only",
                  "expected_outcome": "Expect status: DOWN or degraded latency > 5000ms.",
              },
              {
                  "step_number": 2,
                  "title": "Check Charging Platform Upstream",
                  "description": "Verify if the charging platform is the root cause.",
                  "command": "curl -s http://charging-platform:9090/health | jq .",
                  "action_type": "read_only",
                  "expected_outcome": "Charging platform may show connection timeout.",
              },
              {
                  "step_number": 3,
                  "title": "Review Circuit Breaker State",
                  "description": "Check if billing API circuit breaker is OPEN.",
                  "command": "kubectl exec -n telecom billing-api-pod -- curl localhost:8080/actuator/circuitbreakers",
                  "action_type": "read_only",
                  "expected_outcome": "Circuit breaker state: OPEN (expected at this point).",
              },
              {
                  "step_number": 4,
                  "title": "Retry Stalled VAS Transactions (REQUIRES APPROVAL)",
                  "description": "Retry failed VAS subscription transactions from the dead-letter queue.",
                  "command": "kafka-consumer-groups --bootstrap-server kafka:9092 --group vas-retry --reset-offsets --to-earliest --topic vas.dlq --execute",
                  "action_type": "assisted",
                  "expected_outcome": "Failed transactions reprocessed. Success rate recovers.",
              },
          ],
      },
      "smsc_overload": {
          "title": "SMSC Queue Saturation — SMS/USSD Recovery",
          "steps": [
              {
                  "step_number": 1,
                  "title": "Check SMSC Queue Depth",
                  "description": "Verify current message queue depth in Prometheus.",
                  "command": "smsc_queue_depth{operator='halotel'} | prometheus",
                  "action_type": "read_only",
                  "expected_outcome": "Queue depth > 90% confirms saturation.",
              },
              {
                  "step_number": 2,
                  "title": "Identify Queue Source",
                  "description": "Determine which service is flooding the SMSC queue.",
                  "command": "kafka-consumer-groups --bootstrap-server kafka:9092 --describe --group smsc-consumer",
                  "action_type": "read_only",
                  "expected_outcome": "Identify consumer with highest lag.",
              },
              {
                  "step_number": 3,
                  "title": "Throttle Bulk SMS Sender (REQUIRES APPROVAL)",
                  "description": "Temporarily reduce bulk SMS throughput to allow queue to drain.",
                  "command": "kubectl set env deployment/bulk-sms-sender RATE_LIMIT=100/s  # Current: 1000/s",
                  "action_type": "assisted",
                  "expected_outcome": "Queue depth drops below 50% within 15 minutes.",
              },
          ],
      },
      "generic": {
          "title": "General Incident Investigation Procedure",
          "steps": [
              {
                  "step_number": 1,
                  "title": "Check Service Health Dashboard",
                  "description": "Review Grafana dashboard for all affected services.",
                  "command": None,
                  "action_type": "read_only",
                  "expected_outcome": "Identify which service shows the earliest anomaly.",
              },
              {
                  "step_number": 2,
                  "title": "Review Application Logs",
                  "description": "Query Elasticsearch for ERROR logs in the last 30 minutes.",
                  "command": 'es_query: {"query": {"bool": {"must": [{"match": {"level": "ERROR"}}, {"range": {"@timestamp": {"gte": "now-30m"}}}]}}}',
                  "action_type": "read_only",
                  "expected_outcome": "Find first ERROR occurrence and service stack trace.",
              },
          ],
      },
  }


  async def runbook_node(state: AgentState) -> AgentState:
      """
      Agent 4: Runbook Agent

      In production: uses Qdrant vector similarity to find the best-matching
      runbook from a library of SOPs. Here we use the incident category as the
      primary lookup key with similarity scoring.
      """
      category = state.get("incident_category", "generic")
      logger.info("agent4_start", category=category)

      runbook = RUNBOOKS.get(category, RUNBOOKS["generic"])

      # Flag any ASSISTED steps for safety layer / human approval
      assisted_steps = [s for s in runbook["steps"] if s["action_type"] == "assisted"]
      if assisted_steps:
          pending = state.get("pending_approvals", [])
          for step in assisted_steps:
              pending.append({
                  "id": f"approval-{step['step_number']}",
                  "incident_id": state.get("incident_id", ""),
                  "action": step["title"],
                  "action_class": "assisted",
                  "description": step["description"],
                  "risk_level": "medium",
                  "status": "pending",
              })
          state = {**state, "pending_approvals": pending}

      logger.info("agent4_complete", runbook=runbook["title"], steps=len(runbook["steps"]))

      return {
          **state,
          "runbook_steps": runbook["steps"],
          "runbook_title": runbook["title"],
          "audit_trail": [
              *state.get("audit_trail", []),
              {
                  "agent": "runbook_agent",
                  "timestamp": datetime.utcnow().isoformat(),
                  "action": "runbook_matched",
                  "result": {"runbook": runbook["title"], "steps": len(runbook["steps"]), "assisted": len(assisted_steps)},
              },
          ],
      }
  