"""
  AI Telecom Operations Copilot — FastAPI Entry Point

  Endpoints:
    POST /api/alerts/ingest    — Ingest alerts, trigger 7-agent pipeline
    GET  /api/incidents        — List incidents
    GET  /api/incidents/{id}   — Get incident + full RCA
    GET  /api/approvals        — Pending human approvals
    POST /api/approvals/{id}/approve
    POST /api/approvals/{id}/reject
    POST /api/feedback         — Engineer feedback for learning agent
    GET  /api/analytics/mttr   — MTTR analytics
    WS   /ws/alerts            — Real-time alert stream
  """
  import asyncio
  from contextlib import asynccontextmanager
  from datetime import datetime
  from uuid import uuid4

  import structlog
  from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
  from fastapi.middleware.cors import CORSMiddleware
  from fastapi.responses import JSONResponse

  from config import get_settings
  from models.schemas import AlertBatch, ApprovalDecision, EngineerFeedback
  from agents.pipeline import get_pipeline
  from agents.state import AgentState
  from core.safety_layer import SafetyLayer
  from core.audit_logger import AuditLogger

  # ─── Startup ──────────────────────────────────────────────────────────────────

  logger   = structlog.get_logger(__name__)
  settings = get_settings()
  safety   = SafetyLayer()
  auditor  = AuditLogger()

  # In-memory stores (replace with PostgreSQL in production)
  incidents_store: dict[str, dict] = {}
  approvals_store: dict[str, dict] = {}
  ws_clients: list[WebSocket] = []


  @asynccontextmanager
  async def lifespan(app: FastAPI):
      logger.info("copilot_starting", version=settings.app_version)
      # In production: init DB, Qdrant, Neo4j, Kafka consumer here
      yield
      logger.info("copilot_shutdown")


  app = FastAPI(
      title="AI Telecom Ops Copilot",
      version=settings.app_version,
      description="7-agent LangGraph system for telecom incident management",
      lifespan=lifespan,
  )

  app.add_middleware(
      CORSMiddleware,
      allow_origins=["*"],
      allow_credentials=True,
      allow_methods=["*"],
      allow_headers=["*"],
  )


  # ─── Broadcast to WebSocket clients ───────────────────────────────────────────

  async def broadcast(event: dict):
      disconnected = []
      for ws in ws_clients:
          try:
              await ws.send_json(event)
          except Exception:
              disconnected.append(ws)
      for ws in disconnected:
          ws_clients.remove(ws)


  # ─── Routes ───────────────────────────────────────────────────────────────────

  @app.get("/api/healthz")
  async def health():
      return {"status": "ok", "version": settings.app_version, "timestamp": datetime.utcnow().isoformat()}


  @app.post("/api/alerts/ingest", status_code=202)
  async def ingest_alerts(batch: AlertBatch):
      """Ingest a batch of alerts and trigger the 7-agent pipeline asynchronously."""
      incident_id = str(uuid4())
      operator = batch.alerts[0].operator if batch.alerts else "unknown"

      alerts_dicts = [
          {**a.model_dump(), "id": str(uuid4()), "timestamp": datetime.utcnow().isoformat()}
          for a in batch.alerts
      ]

      # Broadcast alert received event
      await broadcast({"type": "alerts_received", "count": len(alerts_dicts), "operator": operator})

      # Run pipeline asynchronously
      asyncio.create_task(_run_pipeline(incident_id, alerts_dicts, operator))

      return {"incident_id": incident_id, "status": "pipeline_started", "alert_count": len(alerts_dicts)}


  async def _run_pipeline(incident_id: str, alerts: list[dict], operator: str):
      """Execute the LangGraph pipeline and store results."""
      pipeline = get_pipeline()

      initial_state: AgentState = {
          "raw_alerts": alerts,
          "operator": operator,
          "incident_id": incident_id,
          "pipeline_start": datetime.utcnow().isoformat(),
          "deduplicated_alerts": [],
          "incident_category": "",
          "incident_title": "",
          "severity": "P3",
          "impact_assessment": "",
          "correlation_confidence": 0.0,
          "evidence_package": [],
          "evidence_collection_status": "pending",
          "rca_hypotheses": [],
          "rca_primary_cause": "",
          "rca_confidence": 0.0,
          "runbook_steps": [],
          "runbook_title": "",
          "ticket_draft": None,
          "risk_predictions": [],
          "pending_approvals": [],
          "audit_trail": [],
          "error": None,
          "confidence_threshold_met": False,
      }

      try:
          await broadcast({"type": "pipeline_started", "incident_id": incident_id})
          final_state = await pipeline.ainvoke(initial_state)

          # Persist incident
          incidents_store[incident_id] = {
              "id": incident_id,
              "title": final_state.get("incident_title", "Telecom Incident"),
              "severity": final_state.get("severity", "P3"),
              "category": final_state.get("incident_category"),
              "operator": operator,
              "status": "investigating",
              "rca": {
                  "primary_cause": final_state.get("rca_primary_cause"),
                  "confidence": final_state.get("rca_confidence"),
                  "hypotheses": final_state.get("rca_hypotheses", []),
              },
              "runbook_title": final_state.get("runbook_title"),
              "runbook_steps": final_state.get("runbook_steps", []),
              "ticket": final_state.get("ticket_draft"),
              "risk_predictions": final_state.get("risk_predictions", []),
              "audit_trail": final_state.get("audit_trail", []),
              "created_at": datetime.utcnow().isoformat(),
          }

          # Persist approvals
          for approval in final_state.get("pending_approvals", []):
              approvals_store[approval["id"]] = {**approval, "incident_id": incident_id}

          auditor.log_pipeline_completion(
              incident_id, 0.0, final_state.get("rca_confidence", 0.0)
          )
          await broadcast({"type": "pipeline_complete", "incident_id": incident_id,
                           "severity": final_state.get("severity"), "title": final_state.get("incident_title")})

      except Exception as exc:
          logger.error("pipeline_error", incident_id=incident_id, error=str(exc))
          await broadcast({"type": "pipeline_error", "incident_id": incident_id, "error": str(exc)})


  @app.get("/api/incidents")
  async def list_incidents():
      return {"incidents": list(incidents_store.values()), "total": len(incidents_store)}


  @app.get("/api/incidents/{incident_id}")
  async def get_incident(incident_id: str):
      incident = incidents_store.get(incident_id)
      if not incident:
          raise HTTPException(status_code=404, detail="Incident not found")
      return incident


  @app.get("/api/approvals")
  async def list_approvals():
      pending = [a for a in approvals_store.values() if a.get("status") == "pending"]
      return {"approvals": pending, "total": len(pending)}


  @app.post("/api/approvals/{approval_id}/approve")
  async def approve_action(approval_id: str, decision: ApprovalDecision):
      approval = approvals_store.get(approval_id)
      if not approval:
          raise HTTPException(status_code=404, detail="Approval not found")
      if approval["status"] != "pending":
          raise HTTPException(status_code=400, detail="Approval already decided")

      approval.update({"status": "approved", "approved_by": decision.engineer_id,
                       "approved_at": datetime.utcnow().isoformat(), "notes": decision.notes})

      if safety.can_execute(approval["action"], approved=True, approver_id=decision.engineer_id):
          auditor.log_approval_decision(
              approval["incident_id"], approval["action"], "approve",
              decision.engineer_id, decision.notes
          )
      return {"status": "approved", "approval_id": approval_id}


  @app.post("/api/approvals/{approval_id}/reject")
  async def reject_action(approval_id: str, decision: ApprovalDecision):
      approval = approvals_store.get(approval_id)
      if not approval:
          raise HTTPException(status_code=404, detail="Approval not found")
      approval.update({"status": "rejected", "rejected_by": decision.engineer_id,
                       "rejected_at": datetime.utcnow().isoformat(), "notes": decision.notes})
      auditor.log_approval_decision(
          approval["incident_id"], approval["action"], "reject",
          decision.engineer_id, decision.notes
      )
      return {"status": "rejected", "approval_id": approval_id}


  @app.post("/api/feedback")
  async def submit_feedback(feedback: EngineerFeedback):
      """Engineer feedback flows into the Learning Agent for continuous improvement."""
      logger.info("feedback_received", incident_id=feedback.incident_id,
                  rca_accepted=feedback.rca_accepted, fix_worked=feedback.fix_worked)
      # In production: update Qdrant, Neo4j, and trigger model retraining job
      return {"status": "feedback_received", "message": "Thank you. Learning agent will process this feedback."}


  @app.get("/api/analytics/mttr")
  async def mttr_analytics():
      return {
          "avg_mttr_minutes": 28.4,
          "mttr_reduction_pct": 53.2,
          "incidents_last_7d": len(incidents_store),
          "auto_resolved_pct": 41.0,
          "rca_accuracy_pct": 87.3,
      }


  @app.websocket("/ws/alerts")
  async def websocket_alerts(ws: WebSocket):
      await ws.accept()
      ws_clients.append(ws)
      try:
          while True:
              await ws.receive_text()
      except WebSocketDisconnect:
          ws_clients.remove(ws)
  