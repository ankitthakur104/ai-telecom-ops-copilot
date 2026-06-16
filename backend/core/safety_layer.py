"""Safety layer — classifies every action and enforces human-in-the-loop."""
  from enum import Enum
  from datetime import datetime
  from typing import Optional
  import structlog

  logger = structlog.get_logger(__name__)


  class ActionClass(str, Enum):
      READ_ONLY  = "read_only"   # Always allowed — never modifies state
      ASSISTED   = "assisted"    # Requires explicit human approval
      RESTRICTED = "restricted"  # Never allowed — permanently blocked


  # Authoritative action classification table
  SAFETY_RULES: dict[str, ActionClass] = {
      # ── READ_ONLY ─────────────────────────────────────────────────────────
      "query_prometheus_metrics":   ActionClass.READ_ONLY,
      "query_elasticsearch_logs":   ActionClass.READ_ONLY,
      "query_database_readonly":    ActionClass.READ_ONLY,
      "query_incident_history":     ActionClass.READ_ONLY,
      "query_kafka_metrics":        ActionClass.READ_ONLY,
      "query_redis_cache":          ActionClass.READ_ONLY,
      "query_knowledge_graph":      ActionClass.READ_ONLY,
      "fetch_runbook":              ActionClass.READ_ONLY,
      "get_service_health":         ActionClass.READ_ONLY,

      # ── ASSISTED ──────────────────────────────────────────────────────────
      "restart_service":            ActionClass.ASSISTED,
      "retry_provisioning":         ActionClass.ASSISTED,
      "retry_queue_processing":     ActionClass.ASSISTED,
      "reprocess_failed_transactions": ActionClass.ASSISTED,
      "flush_redis_cache":          ActionClass.ASSISTED,
      "increase_connection_pool":   ActionClass.ASSISTED,
      "scale_service_replicas":     ActionClass.ASSISTED,
      "trigger_failover":           ActionClass.ASSISTED,
      "clear_dead_letters":         ActionClass.ASSISTED,

      # ── RESTRICTED ────────────────────────────────────────────────────────
      "delete_database":            ActionClass.RESTRICTED,
      "drop_table":                 ActionClass.RESTRICTED,
      "modify_schema":              ActionClass.RESTRICTED,
      "rotate_credentials":         ActionClass.RESTRICTED,
      "delete_infrastructure":      ActionClass.RESTRICTED,
      "modify_firewall_rules":      ActionClass.RESTRICTED,
      "change_production_config":   ActionClass.RESTRICTED,
      "delete_kafka_topic":         ActionClass.RESTRICTED,
      "truncate_table":             ActionClass.RESTRICTED,
  }


  class SafetyViolationError(Exception):
      """Raised when a RESTRICTED action is attempted."""
      pass


  class SafetyLayer:
      """
      Enforces the core safety principle: the AI copilot is an assistant,
      not an autonomous administrator. Every action flows through this layer.
      """

      def classify(self, action: str) -> ActionClass:
          """
          Classify an action. Unknown actions default to RESTRICTED
          following the principle of least privilege.
          """
          cls = SAFETY_RULES.get(action, ActionClass.RESTRICTED)
          logger.debug("action_classified", action=action, classification=cls.value)
          return cls

      def can_execute(
          self,
          action: str,
          approved: bool = False,
          approver_id: Optional[str] = None,
      ) -> bool:
          """
          Determine if an action can be executed.

          Rules:
          - READ_ONLY: always allowed
          - ASSISTED: only allowed with explicit human approval
          - RESTRICTED: never allowed, raises SafetyViolationError
          """
          cls = self.classify(action)

          if cls == ActionClass.READ_ONLY:
              return True

          if cls == ActionClass.RESTRICTED:
              logger.error(
                  "restricted_action_blocked",
                  action=action,
                  message="This action is permanently blocked by safety policy.",
              )
              raise SafetyViolationError(
                  f"Action '{action}' is RESTRICTED and can never be executed by the AI copilot. "
                  "This includes: database deletion, schema modifications, credential rotation, "
                  "and infrastructure deletion."
              )

          # ASSISTED: requires explicit approval
          if cls == ActionClass.ASSISTED:
              if not approved:
                  logger.warning(
                      "assisted_action_pending_approval",
                      action=action,
                      message="Requires human approval before execution.",
                  )
                  return False
              if not approver_id:
                  logger.error("assisted_action_missing_approver", action=action)
                  return False
              logger.info(
                  "assisted_action_approved",
                  action=action,
                  approver_id=approver_id,
                  approved_at=datetime.utcnow().isoformat(),
              )
              return True

          return False

      def build_approval_request(
          self,
          action: str,
          incident_id: str,
          description: str,
          risk_level: str = "medium",
      ) -> dict:
          """Build a structured approval request for the human-in-the-loop workflow."""
          return {
              "action": action,
              "action_class": "assisted",
              "incident_id": incident_id,
              "description": description,
              "risk_level": risk_level,
              "requested_by": "ai_copilot",
              "requested_at": datetime.utcnow().isoformat(),
              "status": "pending",
          }

      def audit_action(
          self,
          action: str,
          classification: ActionClass,
          executed: bool,
          actor: str,
          details: dict,
      ) -> dict:
          """Create an immutable audit record for every action attempt."""
          return {
              "timestamp": datetime.utcnow().isoformat(),
              "action": action,
              "classification": classification.value,
              "executed": executed,
              "actor": actor,
              "details": details,
          }
  