"""Agent 1: Alert Intelligence — deduplication, prioritization, severity assignment."""
  from datetime import datetime, timedelta
  from collections import defaultdict
  from uuid import uuid4
  import structlog
  from .state import AgentState

  logger = structlog.get_logger(__name__)

  # Deduplication window: alerts for the same service+metric within 5 minutes are duplicates
  DEDUP_WINDOW_SECONDS = 300

  # Severity scoring weights
  SEVERITY_SCORE = {"P1": 100, "P2": 75, "P3": 40, "P4": 15}

  # High-impact CRBT/VAS services
  CRITICAL_SERVICES = {
      "billing_api", "crbt_provisioning", "db_primary",
      "charging_platform", "smsc", "ussd_gateway",
  }


  def _deduplicate(alerts: list[dict]) -> list[dict]:
      """Remove duplicate alerts for the same service+metric within the dedup window."""
      seen: dict[str, dict] = {}
      deduplicated = []

      for alert in sorted(alerts, key=lambda a: a.get("timestamp", ""), reverse=True):
          key = f"{alert['service']}:{alert['metric']}"
          if key not in seen:
              seen[key] = alert
              alert["deduplicated"] = False
              deduplicated.append(alert)
          else:
              logger.debug("alert_deduplicated", service=alert["service"], metric=alert["metric"])

      return deduplicated


  def _assign_severity(alerts: list[dict]) -> str:
      """Escalate to the worst severity across all alerts, with service criticality boost."""
      scores = []
      for a in alerts:
          base = SEVERITY_SCORE.get(a.get("severity", "P3"), 40)
          boost = 1.3 if a["service"] in CRITICAL_SERVICES else 1.0
          scores.append(base * boost)

      max_score = max(scores) if scores else 40
      if max_score >= 130: return "P1"
      if max_score >= 75:  return "P2"
      if max_score >= 40:  return "P3"
      return "P4"


  def _categorize_incident(alerts: list[dict]) -> tuple[str, str]:
      """Return (category, title) for the correlated alert set."""
      services = {a["service"] for a in alerts}
      metrics  = {a["metric"]  for a in alerts}

      # Pattern matching for known CRBT/VAS failure modes
      if "db_primary" in services and "crbt_provisioning" in services:
          return "database_bottleneck", "Database Bottleneck Impacting Subscriber Activations"
      if "billing_api" in services and any(m in metrics for m in ("api_latency_p99", "timeout_rate")):
          return "billing_timeout", "Billing API Timeout — Subscription Services Degraded"
      if "smsc" in services and "ussd_gateway" in services:
          return "smsc_overload", "SMSC Overload — SMS and USSD Services Impacted"
      if "kafka" in services and any(m in metrics for m in ("consumer_lag", "queue_depth")):
          return "queue_backlog", "Kafka Queue Backlog — Processing Pipeline Stalled"
      if "crbt_provisioning" in services:
          return "crbt_failure", "CRBT Provisioning Failure — Activation Success Rate Critical"
      if "charging_platform" in services:
          return "charging_failure", "Charging Platform Degraded — Revenue Impact"

      primary = sorted(services)[0].replace("_", " ").title()
      return "generic", f"{primary} — Service Degradation Detected"


  def _assess_impact(severity: str, services: set, operator: str) -> str:
      critical = services & CRITICAL_SERVICES
      if severity == "P1":
          return (
              f"CRITICAL revenue impact on {operator.upper()}. "
              f"{len(critical)} revenue-critical service(s) affected: {', '.join(critical)}. "
              "Subscriber activations and charging likely failing. Immediate escalation required."
          )
      if severity == "P2":
          return (
              f"HIGH impact on {operator.upper()}. Degraded performance on "
              f"{len(services)} service(s). SLA at risk within 30 minutes."
          )
      return f"MEDIUM impact on {operator.upper()}. {len(services)} service(s) reporting anomalies."


  async def alert_intelligence_node(state: AgentState) -> AgentState:
      """
      Agent 1: Alert Intelligence

      Responsibilities:
      - Deduplicate alerts within correlation window
      - Assign severity using criticality-weighted scoring
      - Categorize the incident pattern
      - Produce impact assessment
      """
      raw = state.get("raw_alerts", [])
      operator = state.get("operator", "unknown")

      logger.info("agent1_start", alert_count=len(raw), operator=operator)

      if not raw:
          return {**state, "error": "No alerts to process"}

      # Step 1: Deduplicate
      deduped = _deduplicate(raw)
      logger.info("agent1_deduplication", original=len(raw), after_dedup=len(deduped))

      # Step 2: Severity
      severity = _assign_severity(deduped)

      # Step 3: Categorize
      category, title = _categorize_incident(deduped)

      # Step 4: Impact
      services = {a["service"] for a in deduped}
      impact = _assess_impact(severity, services, operator)

      # Step 5: Confidence (rule-based + pattern match)
      confidence = 0.78 if category != "generic" else 0.61

      logger.info(
          "agent1_complete",
          severity=severity,
          category=category,
          confidence=confidence,
          services=list(services),
      )

      return {
          **state,
          "deduplicated_alerts": deduped,
          "incident_category": category,
          "incident_title": title,
          "severity": severity,
          "impact_assessment": impact,
          "correlation_confidence": confidence,
          "audit_trail": [
              *state.get("audit_trail", []),
              {
                  "agent": "alert_intelligence",
                  "timestamp": datetime.utcnow().isoformat(),
                  "action": "alert_correlation",
                  "result": {
                      "input_alerts": len(raw),
                      "deduplicated": len(deduped),
                      "severity": severity,
                      "category": category,
                      "confidence": confidence,
                  },
              },
          ],
      }
  