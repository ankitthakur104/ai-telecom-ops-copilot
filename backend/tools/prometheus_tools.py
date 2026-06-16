"""LangChain tools for querying Prometheus metrics (READ_ONLY)."""
  from langchain.tools import tool
  from typing import Optional
  import httpx
  import structlog

  logger = structlog.get_logger(__name__)


  @tool
  async def query_prometheus_metric(
      query: str,
      start_time: Optional[str] = None,
      end_time: Optional[str] = None,
      step: str = "60s",
  ) -> str:
      """
      Query Prometheus metrics using PromQL.
      
      READ_ONLY: This tool only reads metrics, it never modifies system state.
      
      Args:
          query: PromQL expression (e.g. 'rate(crbt_activation_success_total[5m])')
          start_time: ISO timestamp for range query start
          end_time: ISO timestamp for range query end
          step: Resolution step for range queries (default: 60s)
      
      Returns:
          JSON string with metric values
      """
      # In production: connect to real Prometheus instance
      # async with httpx.AsyncClient() as client:
      #     r = await client.get(f"{PROMETHEUS_URL}/api/v1/query", params={"query": query})
      #     return r.text
      
      logger.info("prometheus_query", query=query, action_class="READ_ONLY")
      return f"Prometheus query result for: {query} (connect to real Prometheus in production)"


  @tool
  async def get_service_metrics_snapshot(service: str, operator: str) -> str:
      """
      Get a comprehensive metrics snapshot for a service.
      
      READ_ONLY: Returns current CPU, memory, latency, error rate, throughput.
      
      Args:
          service: Service name (e.g. 'billing_api', 'crbt_provisioning')
          operator: Operator name (e.g. 'halotel', 'ncell', 'vodacom')
      
      Returns:
          Structured metrics snapshot as JSON string
      """
      logger.info("metrics_snapshot", service=service, operator=operator, action_class="READ_ONLY")
      
      # Simulated snapshot — replace with real Prometheus queries
      return f"""{{
    "service": "{service}",
    "operator": "{operator}",
    "cpu_pct": 91.3,
    "memory_pct": 74.2,
    "api_latency_p99_ms": 8420,
    "error_rate_5m_pct": 34.7,
    "throughput_rps": 142,
    "active_connections": 487,
    "timestamp": "2024-01-15T10:30:00Z"
  }}"""


  @tool
  async def get_alert_history(service: str, hours: int = 24) -> str:
      """
      Get recent alert history for a service.
      
      READ_ONLY: Returns historical alerts from Alertmanager.
      
      Args:
          service: Service name
          hours: Number of hours to look back (default: 24)
      
      Returns:
          Alert history as JSON string
      """
      logger.info("alert_history", service=service, hours=hours, action_class="READ_ONLY")
      return f"Alert history for {service} over last {hours}h (connect to Alertmanager in production)"
  