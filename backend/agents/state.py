"""Shared LangGraph state TypedDict flowing through the entire pipeline."""
  from __future__ import annotations
  from datetime import datetime
  from typing import Any, Literal, Optional, TypedDict
  from uuid import uuid4


  class AlertDict(TypedDict):
      id: str
      source: str
      service: str
      operator: str
      severity: str
      metric: str
      value: float
      threshold: float
      unit: str
      timestamp: str
      raw: dict


  class EvidenceDict(TypedDict):
      id: str
      evidence_type: str
      source: str
      content: str
      timestamp: str
      relevance_score: float
      metadata: dict


  class HypothesisDict(TypedDict):
      cause: str
      confidence: float
      evidence_ids: list
      similar_incident_ids: list
      explanation: str


  class RunbookStepDict(TypedDict):
      step_number: int
      title: str
      description: str
      command: Optional[str]
      action_type: str
      expected_outcome: str


  class ApprovalDict(TypedDict):
      id: str
      incident_id: str
      action: str
      action_class: str
      description: str
      risk_level: str
      status: str


  class AgentState(TypedDict):
      # ── Input ──────────────────────────────────────────────────────────────
      raw_alerts: list[AlertDict]
      operator: str

      # ── Agent 1: Alert Intelligence ────────────────────────────────────────
      deduplicated_alerts: list[AlertDict]
      incident_category: str
      incident_title: str
      severity: str
      impact_assessment: str
      correlation_confidence: float

      # ── Agent 2: Evidence Collection ───────────────────────────────────────
      evidence_package: list[EvidenceDict]
      evidence_collection_status: str

      # ── Agent 3: Root Cause Analysis ───────────────────────────────────────
      rca_hypotheses: list[HypothesisDict]
      rca_primary_cause: str
      rca_confidence: float

      # ── Agent 4: Runbook ───────────────────────────────────────────────────
      runbook_steps: list[RunbookStepDict]
      runbook_title: str

      # ── Agent 5: Ticket Automation ─────────────────────────────────────────
      ticket_draft: Optional[dict]

      # ── Agent 6: Predictive Failure ────────────────────────────────────────
      risk_predictions: list[dict]

      # ── Safety & Audit ─────────────────────────────────────────────────────
      pending_approvals: list[ApprovalDict]
      audit_trail: list[dict]

      # ── Pipeline Control ───────────────────────────────────────────────────
      incident_id: str
      pipeline_start: str
      error: Optional[str]
      confidence_threshold_met: bool
  