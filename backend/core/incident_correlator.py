"""Alert correlation engine — converts alert storms into meaningful incidents."""
  from datetime import datetime, timedelta
  from collections import defaultdict
  from typing import NamedTuple
  import structlog

  logger = structlog.get_logger(__name__)


  # Service dependency graph for telecom platforms
  SERVICE_DEPENDENCIES: dict[str, list[str]] = {
      "crbt_provisioning":  ["billing_api", "db_primary", "redis_cache"],
      "ussd_gateway":       ["db_primary", "smsc", "billing_api"],
      "smsc":               ["db_primary", "kafka"],
      "billing_api":        ["db_primary", "redis_cache", "charging_platform"],
      "charging_platform":  ["db_primary", "external_gateway"],
      "vas_subscription":   ["billing_api", "smsc", "db_primary"],
      "crm_api":            ["db_primary", "redis_cache"],
      "content_delivery":   ["db_primary", "cdn", "storage"],
      "kafka":              ["zookeeper"],
      "db_primary":         [],
  }

  # Known incident patterns for CRBT/VAS platforms
  KNOWN_PATTERNS: list[dict] = [
      {
          "name": "Database Bottleneck — Activation Cascade",
          "triggers": ["db_primary", "crbt_provisioning"],
          "metrics": ["cpu_utilization", "activation_success_rate", "api_latency_p99"],
          "confidence_boost": 0.15,
      },
      {
          "name": "Billing API Timeout — VAS Failure",
          "triggers": ["billing_api", "vas_subscription"],
          "metrics": ["api_latency_p99", "timeout_rate", "error_rate"],
          "confidence_boost": 0.18,
      },
      {
          "name": "SMSC Overload — SMS Delivery Failure",
          "triggers": ["smsc", "ussd_gateway"],
          "metrics": ["queue_depth", "delivery_failure_rate"],
          "confidence_boost": 0.12,
      },
      {
          "name": "Kafka Lag — Queue Backlog Cascade",
          "triggers": ["kafka", "crbt_provisioning"],
          "metrics": ["consumer_lag", "queue_depth", "processing_rate"],
          "confidence_boost": 0.10,
      },
  ]

  CORRELATION_WINDOW_SECONDS = 300  # 5 minutes


  class CorrelationResult(NamedTuple):
      incident_title: str
      category: str
      severity: str
      affected_services: list[str]
      confidence: float
      root_service: str
      impact_assessment: str


  class IncidentCorrelator:
      """
      Converts a batch of raw alerts into a single correlated incident.

      Algorithm:
      1. Temporal filtering — only alerts within the correlation window
      2. Service dependency traversal — find the upstream root service
      3. Known pattern matching — boost confidence if pattern matches
      4. Severity escalation — worst alert severity becomes incident severity
      """

      def correlate(self, alerts: list[dict]) -> CorrelationResult:
          if not alerts:
              raise ValueError("Cannot correlate empty alert list")

          services = list({a["service"] for a in alerts})
          metrics = list({a["metric"] for a in alerts})
          severity = self._escalate_severity([a.get("severity", "P3") for a in alerts])
          operator = alerts[0].get("operator", "unknown")

          # Find likely root service via dependency graph
          root_service = self._find_root_service(services)

          # Match known patterns
          matched_pattern = None
          base_confidence = 0.72
          for pattern in KNOWN_PATTERNS:
              triggers_hit = sum(1 for t in pattern["triggers"] if t in services)
              metrics_hit  = sum(1 for m in pattern["metrics"]  if m in metrics)
              if triggers_hit >= 1 and metrics_hit >= 1:
                  matched_pattern = pattern
                  base_confidence += pattern["confidence_boost"] * (triggers_hit + metrics_hit) / (
                      len(pattern["triggers"]) + len(pattern["metrics"])
                  )
                  break

          base_confidence = min(base_confidence, 0.97)

          if matched_pattern:
              title = matched_pattern["name"]
              category = "known_pattern"
          else:
              title = f"{root_service.replace('_', ' ').title()} Incident — {len(services)} Services Affected"
              category = "unknown"

          impact = self._assess_impact(severity, services, operator)

          logger.info(
              "incident_correlated",
              title=title,
              services=services,
              root_service=root_service,
              confidence=round(base_confidence, 3),
              pattern=matched_pattern["name"] if matched_pattern else None,
          )

          return CorrelationResult(
              incident_title=title,
              category=category,
              severity=severity,
              affected_services=services,
              confidence=round(base_confidence, 3),
              root_service=root_service,
              impact_assessment=impact,
          )

      def _find_root_service(self, services: list[str]) -> str:
          """Find the service most likely to be the root cause (fewest dependencies that are also affected)."""
          scores = {}
          for svc in services:
              deps = SERVICE_DEPENDENCIES.get(svc, [])
              affected_deps = sum(1 for d in deps if d in services)
              # Higher score = more downstream (more likely a symptom, not root)
              scores[svc] = affected_deps
          # Root service has fewest upstream dependencies in the affected set
          return min(scores, key=scores.get)

      def _escalate_severity(self, severities: list[str]) -> str:
          order = {"P1": 0, "P2": 1, "P3": 2, "P4": 3}
          return min(severities, key=lambda s: order.get(s, 3))

      def _assess_impact(self, severity: str, services: list[str], operator: str) -> str:
          crbt_affected = any("crbt" in s or "provisioning" in s for s in services)
          billing_affected = "billing_api" in services
          high_value = severity in ("P1", "P2")

          if high_value and billing_affected:
              return f"CRITICAL: Revenue-impacting failure on {operator}. Charging and subscription services degraded."
          if crbt_affected:
              return f"HIGH: CRBT subscriber provisioning degraded on {operator}. New activations and renewals failing."
          return f"MEDIUM: Service degradation on {operator}. {len(services)} component(s) affected."
  