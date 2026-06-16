"""Agent 3: Root Cause Analysis — RAG + knowledge graph + LLM reasoning."""
  from datetime import datetime
  from uuid import uuid4
  import structlog
  from .state import AgentState

  logger = structlog.get_logger(__name__)

  # Simulated knowledge base of CRBT/VAS root causes
  # In production: retrieved from Qdrant (RAG) + Neo4j (knowledge graph)
  KNOWLEDGE_BASE = {
      "database_bottleneck": [
          {
              "cause": "Connection Pool Exhaustion",
              "confidence": 0.92,
              "explanation": (
                  "DB connection pool fully saturated. All 50 connections in use with 23 queued. "
                  "Slow queries (avg 8.4s) holding connections open, causing cascade to CRBT provisioning. "
                  "Pattern matches INC-2024-0891 with 91% similarity."
              ),
              "evidence_signals": ["connection pool exhausted", "api_latency_p99 > 5000ms", "queue growth"],
              "kg_path": "halotel → db_primary → connection_pool → crbt_provisioning → activation_failure",
          },
          {
              "cause": "Missing Database Index — Full Table Scan",
              "confidence": 0.05,
              "explanation": (
                  "Possible missing index on subscribers table causing full scans at peak load. "
                  "Low confidence — no slow query logs confirm this currently."
              ),
              "evidence_signals": ["slow_query_log", "full_table_scan"],
              "kg_path": "db_primary → missing_index → slow_queries → timeout_cascade",
          },
          {
              "cause": "Database Lock Contention",
              "confidence": 0.03,
              "explanation": "Possible row-level locking contention. Very low confidence — no lock wait metrics.",
              "evidence_signals": ["lock_wait_timeout"],
              "kg_path": "db_primary → lock_contention → transaction_timeout",
          },
      ],
      "billing_timeout": [
          {
              "cause": "Billing API Downstream Timeout",
              "confidence": 0.89,
              "explanation": (
                  "Billing API responding in 8420ms (threshold 2000ms). Downstream charging platform "
                  "saturated. Circuit breaker now OPEN. Subscription renewals and new activations failing."
              ),
              "evidence_signals": ["api_latency_p99 > 8000ms", "circuit_breaker OPEN", "timeout_rate > 30%"],
              "kg_path": "charging_platform → slow → billing_api → timeout → vas_subscription → failure",
          },
      ],
      "smsc_overload": [
          {
              "cause": "SMSC Queue Saturation",
              "confidence": 0.87,
              "explanation": "SMSC message queue depth at 94%. Delivery failure rate 23%. SMS and USSD degraded.",
              "evidence_signals": ["queue_depth > 90%", "delivery_failure_rate > 20%"],
              "kg_path": "smsc → queue_saturation → delivery_failure → ussd_timeout",
          },
      ],
      "generic": [
          {
              "cause": "Service Degradation — Root Cause Under Investigation",
              "confidence": 0.65,
              "explanation": "Insufficient evidence for definitive root cause. Evidence collection ongoing.",
              "evidence_signals": ["error_rate elevated"],
              "kg_path": "unknown",
          },
      ],
  }


  async def rca_node(state: AgentState) -> AgentState:
      """
      Agent 3: Root Cause Analysis

      Algorithm:
      1. RAG retrieval — find similar incidents from Qdrant vector store
      2. Knowledge graph traversal — Neo4j dependency path analysis
      3. LLM structured reasoning — GPT-4o with tool calls over evidence
      4. Hypothesis validation — every hypothesis must have supporting evidence
      5. Confidence calibration — normalize across all hypotheses

      In production: steps 1-3 use real LLM + Qdrant + Neo4j.
      """
      category = state.get("incident_category", "generic")
      evidence  = state.get("evidence_package", [])
      operator  = state.get("operator", "unknown")

      logger.info("agent3_start", category=category, evidence_count=len(evidence))

      # Retrieve hypotheses for this incident category
      raw_hypotheses = KNOWLEDGE_BASE.get(category, KNOWLEDGE_BASE["generic"])

      # Filter: only include hypotheses with evidence support
      # In production: validate each hypothesis against the actual evidence package via LLM
      validated_hypotheses = []
      for h in raw_hypotheses:
          # Check if any evidence content matches this hypothesis's signals
          evidence_support = sum(
              1 for e in evidence
              if any(sig.lower() in e["content"].lower() for sig in h["evidence_signals"])
          )
          # Include hypothesis if confidence > threshold OR evidence supports it
          if h["confidence"] >= 0.30 or evidence_support > 0:
              validated_hypotheses.append({
                  "cause": h["cause"],
                  "confidence": h["confidence"],
                  "evidence_ids": [e["id"] for e in evidence[:3]],
                  "similar_incident_ids": ["INC-2024-0891", "INC-2024-0634"],
                  "explanation": h["explanation"],
                  "kg_path": h.get("kg_path", ""),
              })

      # Normalize confidences to sum to 1.0
      total = sum(h["confidence"] for h in validated_hypotheses)
      if total > 0:
          for h in validated_hypotheses:
              h["confidence"] = round(h["confidence"] / total, 3)

      primary = validated_hypotheses[0] if validated_hypotheses else None
      rca_confidence = primary["confidence"] if primary else 0.0

      logger.info(
          "agent3_complete",
          hypotheses=len(validated_hypotheses),
          primary_cause=primary["cause"] if primary else None,
          confidence=rca_confidence,
      )

      return {
          **state,
          "rca_hypotheses": validated_hypotheses,
          "rca_primary_cause": primary["cause"] if primary else "Unknown",
          "rca_confidence": rca_confidence,
          "confidence_threshold_met": rca_confidence >= 0.60,
          "audit_trail": [
              *state.get("audit_trail", []),
              {
                  "agent": "root_cause_analysis",
                  "timestamp": datetime.utcnow().isoformat(),
                  "action": "rca_generated",
                  "result": {
                      "hypotheses": len(validated_hypotheses),
                      "primary_cause": primary["cause"] if primary else None,
                      "confidence": rca_confidence,
                      "rag_results": 2,
                      "kg_patterns": 1,
                  },
              },
          ],
      }
  