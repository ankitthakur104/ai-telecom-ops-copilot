"""Pydantic models for the AI Telecom Operations Copilot."""
  from __future__ import annotations
  from datetime import datetime
  from typing import Any, Literal, Optional
  from pydantic import BaseModel, Field
  from uuid import UUID, uuid4


  # ─── Alert Models ─────────────────────────────────────────────────────────────

  class AlertIn(BaseModel):
      source: Literal["prometheus", "elk", "kafka", "app", "snmp"] = "prometheus"
      service: str = Field(..., examples=["billing_api", "crbt_provisioning", "smsc", "ussd_gateway"])
      operator: Literal["halotel", "ncell", "vodacom", "generic"] = "generic"
      severity: Literal["P1", "P2", "P3", "P4"] = "P3"
      metric: str = Field(..., examples=["api_latency_p99", "activation_success_rate", "cpu_utilization"])
      value: float
      threshold: float
      unit: str = ""
      raw: dict[str, Any] = Field(default_factory=dict)


  class Alert(AlertIn):
      id: str = Field(default_factory=lambda: str(uuid4()))
      timestamp: datetime = Field(default_factory=datetime.utcnow)
      deduplicated: bool = False
      correlated_incident_id: Optional[str] = None


  class AlertBatch(BaseModel):
      alerts: list[AlertIn] = Field(..., min_length=1, max_length=100)


  # ─── Evidence Models ──────────────────────────────────────────────────────────

  class Evidence(BaseModel):
      id: str = Field(default_factory=lambda: str(uuid4()))
      evidence_type: Literal["log", "metric", "trace", "historical_incident", "kg_pattern"]
      source: str
      content: str
      timestamp: datetime = Field(default_factory=datetime.utcnow)
      relevance_score: float = Field(ge=0.0, le=1.0)
      metadata: dict[str, Any] = Field(default_factory=dict)


  # ─── RCA Models ───────────────────────────────────────────────────────────────

  class RcaHypothesis(BaseModel):
      cause: str
      confidence: float = Field(ge=0.0, le=1.0)
      evidence_ids: list[str] = Field(default_factory=list)
      similar_incident_ids: list[str] = Field(default_factory=list)
      explanation: str = ""


  class RcaResult(BaseModel):
      incident_id: str
      hypotheses: list[RcaHypothesis]
      primary_cause: str
      confidence: float
      generated_at: datetime = Field(default_factory=datetime.utcnow)
      evidence_count: int = 0
      knowledge_graph_patterns: list[dict] = Field(default_factory=list)


  # ─── Incident Models ──────────────────────────────────────────────────────────

  class Incident(BaseModel):
      id: str = Field(default_factory=lambda: str(uuid4()))
      title: str
      category: str
      severity: Literal["P1", "P2", "P3", "P4"]
      operator: str
      affected_services: list[str] = Field(default_factory=list)
      impact_assessment: str = ""
      alert_ids: list[str] = Field(default_factory=list)
      status: Literal["open", "investigating", "resolved", "closed"] = "open"
      rca: Optional[RcaResult] = None
      runbook_steps: list[dict] = Field(default_factory=list)
      ticket: Optional[dict] = None
      created_at: datetime = Field(default_factory=datetime.utcnow)
      resolved_at: Optional[datetime] = None
      mttr_minutes: Optional[float] = None


  # ─── Runbook Models ───────────────────────────────────────────────────────────

  class RunbookStep(BaseModel):
      step_number: int
      title: str
      description: str
      command: Optional[str] = None
      action_type: Literal["read_only", "assisted", "verify"] = "read_only"
      expected_outcome: str = ""


  class RunbookMatch(BaseModel):
      runbook_id: str
      title: str
      similarity_score: float
      steps: list[RunbookStep]


  # ─── Ticket Models ────────────────────────────────────────────────────────────

  class TicketDraft(BaseModel):
      summary: str
      description: str
      priority: Literal["Critical", "High", "Medium", "Low"]
      component: str
      operator: str
      impact: str
      timeline: str
      rca_summary: str
      recommendations: list[str] = Field(default_factory=list)
      labels: list[str] = Field(default_factory=list)


  # ─── Approval Models ──────────────────────────────────────────────────────────

  class ApprovalRequest(BaseModel):
      id: str = Field(default_factory=lambda: str(uuid4()))
      incident_id: str
      action: str
      action_class: Literal["assisted"]
      description: str
      risk_level: Literal["low", "medium", "high"]
      requested_by: str = "ai_copilot"
      created_at: datetime = Field(default_factory=datetime.utcnow)
      status: Literal["pending", "approved", "rejected"] = "pending"
      approved_by: Optional[str] = None
      approved_at: Optional[datetime] = None
      notes: str = ""


  class ApprovalDecision(BaseModel):
      decision: Literal["approve", "reject"]
      engineer_id: str
      notes: str = ""


  # ─── Feedback Models ──────────────────────────────────────────────────────────

  class EngineerFeedback(BaseModel):
      incident_id: str
      rca_accepted: bool
      actual_cause: Optional[str] = None
      fix_worked: bool = True
      notes: str = ""
      engineer_id: str


  # ─── Prediction Models ────────────────────────────────────────────────────────

  class FailurePrediction(BaseModel):
      service: str
      operator: str
      failure_probability: float = Field(ge=0.0, le=1.0)
      expected_failure_in_hours: Optional[float] = None
      risk_level: Literal["critical", "high", "medium", "low"]
      contributing_signals: list[str] = Field(default_factory=list)
      recommended_action: str = ""
      predicted_at: datetime = Field(default_factory=datetime.utcnow)


  # ─── Agent State ──────────────────────────────────────────────────────────────

  class AgentState(BaseModel):
      """Shared state flowing through the LangGraph pipeline."""
      # Input
      raw_alerts: list[Alert] = Field(default_factory=list)
      operator: str = ""

      # Agent 1: Alert Intelligence
      deduplicated_alerts: list[Alert] = Field(default_factory=list)
      incident_category: str = ""
      severity: str = "P3"
      impact_assessment: str = ""
      correlation_confidence: float = 0.0

      # Agent 2: Evidence Collection
      evidence_package: list[Evidence] = Field(default_factory=list)
      evidence_collection_status: str = "pending"

      # Agent 3: Root Cause Analysis
      rca_hypotheses: list[RcaHypothesis] = Field(default_factory=list)
      rca_confidence: float = 0.0

      # Agent 4: Runbook
      runbook_matches: list[RunbookMatch] = Field(default_factory=list)

      # Agent 5: Ticket
      ticket_draft: Optional[TicketDraft] = None

      # Agent 6: Predictive Failure
      risk_predictions: list[FailurePrediction] = Field(default_factory=list)

      # Safety & Audit
      pending_approvals: list[ApprovalRequest] = Field(default_factory=list)
      audit_trail: list[dict] = Field(default_factory=list)

      # Control
      incident_id: str = Field(default_factory=lambda: str(uuid4()))
      pipeline_start: datetime = Field(default_factory=datetime.utcnow)
      error: Optional[str] = None
      confidence_threshold_met: bool = False
  