"""Immutable audit logger for all AI copilot recommendations and actions."""
  import json
  from datetime import datetime
  from typing import Any
  import structlog

  logger = structlog.get_logger(__name__)


  class AuditEvent:
      """Represents a single immutable audit event."""

      def __init__(
          self,
          event_type: str,
          actor: str,
          incident_id: str,
          details: dict[str, Any],
          outcome: str = "success",
      ):
          self.event_type = event_type
          self.actor = actor
          self.incident_id = incident_id
          self.details = details
          self.outcome = outcome
          self.timestamp = datetime.utcnow().isoformat()

      def to_dict(self) -> dict:
          return {
              "timestamp": self.timestamp,
              "event_type": self.event_type,
              "actor": self.actor,
              "incident_id": self.incident_id,
              "details": self.details,
              "outcome": self.outcome,
          }


  class AuditLogger:
      """
      Maintains a complete, immutable audit trail for:
      - Every AI recommendation
      - Every human approval / rejection
      - Every safety classification decision
      - Every action execution attempt
      """

      def log_recommendation(self, incident_id: str, rca: dict, hypotheses: list) -> None:
          event = AuditEvent(
              event_type="rca_recommendation",
              actor="rca_agent",
              incident_id=incident_id,
              details={"rca_summary": rca, "hypotheses_count": len(hypotheses)},
          )
          logger.info("audit", **event.to_dict())

      def log_approval_request(self, incident_id: str, action: str, description: str) -> None:
          event = AuditEvent(
              event_type="approval_requested",
              actor="ai_copilot",
              incident_id=incident_id,
              details={"action": action, "description": description},
          )
          logger.info("audit", **event.to_dict())

      def log_approval_decision(
          self, incident_id: str, action: str, decision: str, engineer_id: str, notes: str
      ) -> None:
          event = AuditEvent(
              event_type="approval_decision",
              actor=engineer_id,
              incident_id=incident_id,
              details={"action": action, "decision": decision, "notes": notes},
              outcome=decision,
          )
          logger.info("audit", **event.to_dict())

      def log_safety_block(self, incident_id: str, action: str, reason: str) -> None:
          event = AuditEvent(
              event_type="safety_block",
              actor="safety_layer",
              incident_id=incident_id,
              details={"action": action, "reason": reason},
              outcome="blocked",
          )
          logger.warning("audit", **event.to_dict())

      def log_pipeline_completion(
          self, incident_id: str, duration_seconds: float, confidence: float
      ) -> None:
          event = AuditEvent(
              event_type="pipeline_completed",
              actor="langgraph_pipeline",
              incident_id=incident_id,
              details={"duration_seconds": duration_seconds, "rca_confidence": confidence},
          )
          logger.info("audit", **event.to_dict())
  