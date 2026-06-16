"""LangGraph pipeline — wires all 7 agents into a directed state graph."""
  from langgraph.graph import StateGraph, END
  from .state import AgentState
  from .alert_intelligence  import alert_intelligence_node
  from .evidence_collection import evidence_collection_node
  from .root_cause_analysis import rca_node
  from .runbook_agent        import runbook_node
  from .ticket_automation    import ticket_node
  from .predictive_failure   import predictive_node
  from .learning_agent       import learning_node
  import structlog

  logger = structlog.get_logger(__name__)


  def _should_run_predictive(state: AgentState) -> str:
      """Run predictive analysis in parallel only for P1/P2 incidents."""
      return "predictive" if state.get("severity") in ("P1", "P2") else "evidence"


  def _check_confidence(state: AgentState) -> str:
      """Route to learning agent after ticket — always runs."""
      return "learning"


  def build_pipeline() -> StateGraph:
      """
      Build and compile the 7-agent LangGraph pipeline.

      Pipeline flow:
          alert_intelligence
              ├─► predictive_failure (P1/P2 only, parallel)
              └─► evidence_collection
                      └─► root_cause_analysis
                              └─► runbook_agent
                                      └─► ticket_automation
                                              └─► learning_agent
                                                      └─► END
      """
      graph = StateGraph(AgentState)

      # Register all agent nodes
      graph.add_node("alert_intelligence",  alert_intelligence_node)
      graph.add_node("evidence_collection", evidence_collection_node)
      graph.add_node("root_cause_analysis", rca_node)
      graph.add_node("runbook_agent",       runbook_node)
      graph.add_node("ticket_automation",   ticket_node)
      graph.add_node("predictive_failure",  predictive_node)
      graph.add_node("learning_agent",      learning_node)

      # Entry point
      graph.set_entry_point("alert_intelligence")

      # Conditional branch: P1/P2 triggers predictive analysis in parallel path
      graph.add_conditional_edges(
          "alert_intelligence",
          _should_run_predictive,
          {
              "predictive": "predictive_failure",
              "evidence":   "evidence_collection",
          },
      )

      # Predictive rejoins main pipeline at evidence collection
      graph.add_edge("predictive_failure",  "evidence_collection")

      # Main sequential pipeline
      graph.add_edge("evidence_collection", "root_cause_analysis")
      graph.add_edge("root_cause_analysis", "runbook_agent")
      graph.add_edge("runbook_agent",       "ticket_automation")
      graph.add_edge("ticket_automation",   "learning_agent")
      graph.add_edge("learning_agent",      END)

      compiled = graph.compile()
      logger.info("pipeline_built", nodes=list(graph.nodes))
      return compiled


  # Singleton pipeline instance
  _pipeline = None

  def get_pipeline():
      global _pipeline
      if _pipeline is None:
          _pipeline = build_pipeline()
      return _pipeline
  