"""Agent 7: Learning Agent — continuous improvement from engineer feedback."""
  from datetime import datetime
  import structlog
  from .state import AgentState

  logger = structlog.get_logger(__name__)


  async def learning_node(state: AgentState) -> AgentState:
      """
      Agent 7: Learning Agent

      Closes the feedback loop by persisting:
      - Which RCA hypotheses engineers accepted/rejected
      - Which runbook steps succeeded/failed
      - Which tickets were accurate vs required correction
      - Timing and MTTR data for model retraining

      In production:
      - Feedback stored in PostgreSQL (incidents + feedback tables)
      - Accepted RCA patterns → added to Qdrant vector store
      - Rejected patterns → negative examples for reranking
      - Knowledge graph updated: incident → root_cause → fix relationships
      - LSTM models retrained weekly on updated incident history
      - Confidence weights adjusted based on engineer agreement rate

      This agent runs asynchronously and does not block the main pipeline.
      The feedback loop completes when engineers submit feedback via /api/feedback.
      """
      incident_id = state.get("incident_id", "")
      category    = state.get("incident_category", "generic")
      confidence  = state.get("rca_confidence", 0.0)
      hypotheses  = state.get("rca_hypotheses", [])
      operator    = state.get("operator", "unknown")

      pipeline_start = state.get("pipeline_start", datetime.utcnow().isoformat())
      try:
          start_dt = datetime.fromisoformat(pipeline_start)
          duration = (datetime.utcnow() - start_dt).total_seconds()
      except Exception:
          duration = 0.0

      # Prepare learning record for persistence
      learning_record = {
          "incident_id": incident_id,
          "operator": operator,
          "category": category,
          "rca_confidence": confidence,
          "hypotheses_count": len(hypotheses),
          "pipeline_duration_seconds": round(duration, 2),
          "status": "awaiting_engineer_feedback",
          "created_at": datetime.utcnow().isoformat(),
      }

      logger.info(
          "agent7_learning_record_created",
          incident_id=incident_id,
          duration_seconds=round(duration, 2),
          confidence=confidence,
          category=category,
      )

      # In production: asyncio.create_task(persist_learning_record(learning_record))
      # This writes to PostgreSQL and queues a Qdrant upsert job

      return {
          **state,
          "audit_trail": [
              *state.get("audit_trail", []),
              {
                  "agent": "learning_agent",
                  "timestamp": datetime.utcnow().isoformat(),
                  "action": "learning_record_created",
                  "result": learning_record,
              },
          ],
      }
  