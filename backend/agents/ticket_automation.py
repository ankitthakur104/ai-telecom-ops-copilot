"""Agent 5: Ticket Automation — generates structured Jira/ServiceNow tickets."""
  from datetime import datetime
  import structlog
  from .state import AgentState

  logger = structlog.get_logger(__name__)

  PRIORITY_MAP = {"P1": "Critical", "P2": "High", "P3": "Medium", "P4": "Low"}
  LABEL_MAP = {
      "database_bottleneck": ["database", "connection-pool", "crbt", "p1-incident"],
      "billing_timeout":     ["billing", "timeout", "vas", "revenue-impact"],
      "smsc_overload":       ["smsc", "sms", "ussd", "queue"],
      "crbt_failure":        ["crbt", "provisioning", "activation"],
      "generic":             ["telecom-ops", "investigation-required"],
  }


  async def ticket_node(state: AgentState) -> AgentState:
      """
      Agent 5: Ticket Automation

      Generates a fully structured Jira/ServiceNow ticket from:
      - Incident metadata (severity, operator, services)
      - Evidence package summary
      - RCA hypotheses
      - Runbook steps

      In production: calls Jira REST API or ServiceNow API to create the ticket.
      """
      incident_id  = state.get("incident_id", "")
      title        = state.get("incident_title", "Telecom Incident")
      severity     = state.get("severity", "P3")
      operator     = state.get("operator", "unknown")
      category     = state.get("incident_category", "generic")
      impact       = state.get("impact_assessment", "")
      hypotheses   = state.get("rca_hypotheses", [])
      runbook_steps = state.get("runbook_steps", [])
      evidence     = state.get("evidence_package", [])

      logger.info("agent5_start", incident_id=incident_id, severity=severity)

      primary = hypotheses[0] if hypotheses else None

      # Build structured ticket
      timeline = (
          f"- {datetime.utcnow().strftime('%H:%M:%S')} UTC: Incident detected by AI Copilot\n"
          f"- {datetime.utcnow().strftime('%H:%M:%S')} UTC: Evidence collected ({len(evidence)} data points)\n"
          f"- {datetime.utcnow().strftime('%H:%M:%S')} UTC: RCA completed (confidence: {state.get('rca_confidence', 0):.0%})\n"
          f"- Ticket auto-generated. Awaiting L2 engineer assignment."
      )

      rca_summary = (
          f"Primary Cause: {primary['cause']} (confidence: {primary['confidence']:.0%})\n"
          f"Explanation: {primary['explanation']}"
      ) if primary else "RCA in progress."

      recommendations = []
      for step in runbook_steps:
          if step["action_type"] == "read_only":
              recommendations.append(f"✓ [READ] {step['title']}: {step['description']}")
          elif step["action_type"] == "assisted":
              recommendations.append(f"⚠ [APPROVAL REQUIRED] {step['title']}: {step['description']}")

      ticket = {
          "summary": f"[{severity}] {title} — {operator.upper()}",
          "description": (
              f"## Incident Summary\n{impact}\n\n"
              f"## Timeline\n{timeline}\n\n"
              f"## Root Cause Analysis\n{rca_summary}\n\n"
              f"## Evidence Collected\n"
              + "\n".join(f"- {e['source']}: {e['content'][:100]}..." for e in evidence[:5])
              + f"\n\n## Recommended Actions\n"
              + "\n".join(recommendations)
          ),
          "priority": PRIORITY_MAP.get(severity, "Medium"),
          "component": operator.upper(),
          "operator": operator,
          "impact": impact,
          "timeline": timeline,
          "rca_summary": rca_summary,
          "recommendations": recommendations,
          "labels": LABEL_MAP.get(category, ["telecom-ops"]),
          "incident_id": incident_id,
          "created_at": datetime.utcnow().isoformat(),
          "reporter": "AI Telecom Ops Copilot",
      }

      logger.info("agent5_complete", priority=ticket["priority"], labels=ticket["labels"])

      return {
          **state,
          "ticket_draft": ticket,
          "audit_trail": [
              *state.get("audit_trail", []),
              {
                  "agent": "ticket_automation",
                  "timestamp": datetime.utcnow().isoformat(),
                  "action": "ticket_generated",
                  "result": {"priority": ticket["priority"], "labels": ticket["labels"]},
              },
          ],
      }
  