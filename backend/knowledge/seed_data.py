"""
  Telecom incident knowledge base seed data.

  Loaded into Qdrant (vector store) and Neo4j (knowledge graph) on first startup.
  These are real-world CRBT/VAS incident patterns compiled from operations experience.
  """

  INCIDENT_KNOWLEDGE_BASE = [
      {
          "id": "KB-001",
          "title": "DB Connection Pool Exhaustion — CRBT Activation Failure",
          "category": "database_bottleneck",
          "operators": ["halotel", "ncell", "vodacom"],
          "symptoms": [
              "activation_success_rate < 30%",
              "api_latency_p99 > 5000ms",
              "active_connections > 95% of pool size",
              "queue depth growing",
          ],
          "root_cause": "PgBouncer connection pool exhausted due to slow queries holding connections",
          "resolution": "Increase pool_size from 50 to 150; add read replica; optimize slow queries",
          "fix_commands": [
              "pgbouncer_reload_config --pool-size=150",
              "CREATE INDEX CONCURRENTLY idx_subs_status ON subscribers(status, created_at);",
          ],
          "mttr_minutes": 47,
          "recurrence": "monthly",
          "prevention": "Set pool alert at 80% utilization; weekly slow query review",
      },
      {
          "id": "KB-002",
          "title": "Billing API Timeout — VAS Subscription Failure",
          "category": "billing_timeout",
          "operators": ["halotel", "vodacom"],
          "symptoms": [
              "billing_api latency > 5000ms",
              "circuit_breaker: OPEN",
              "vas_subscription_failure_rate > 20%",
          ],
          "root_cause": "Downstream charging platform DB saturation causing timeout cascade",
          "resolution": "Add charging DB read replica; increase billing_api timeout to 15s; retry VAS dead-letter queue",
          "fix_commands": [
              "kafka-consumer-groups --reset-offsets --to-earliest --topic vas.dlq --execute",
          ],
          "mttr_minutes": 112,
          "recurrence": "quarterly",
          "prevention": "Charging platform separate DB; async billing with retry queue",
      },
      {
          "id": "KB-003",
          "title": "SMSC Queue Saturation — SMS/USSD Delivery Failure",
          "category": "smsc_overload",
          "operators": ["ncell", "vodacom"],
          "symptoms": [
              "smsc_queue_depth > 85%",
              "delivery_failure_rate > 20%",
              "ussd_timeout_rate increasing",
          ],
          "root_cause": "Bulk SMS campaign saturating SMSC queue, starving transactional messages",
          "resolution": "Throttle bulk SMS sender; prioritize transactional messages",
          "fix_commands": [
              "kubectl set env deployment/bulk-sms-sender RATE_LIMIT=100/s",
          ],
          "mttr_minutes": 35,
          "recurrence": "bi-weekly (campaign days)",
          "prevention": "Separate bulk vs transactional SMSC routing; campaign scheduling",
      },
      {
          "id": "KB-004",
          "title": "Kafka Consumer Lag — Processing Pipeline Stalled",
          "category": "queue_backlog",
          "operators": ["halotel", "ncell", "vodacom"],
          "symptoms": [
              "kafka_consumer_lag > 100000",
              "processing_rate < 10% of normal",
              "crbt_renewal_failure_rate increasing",
          ],
          "root_cause": "Consumer group rebalancing after pod restart causing temporary processing halt",
          "resolution": "Increase consumer replicas; check rebalance logs; reset offset if needed",
          "fix_commands": [
              "kubectl scale deployment/crbt-consumer --replicas=6",
          ],
          "mttr_minutes": 22,
          "recurrence": "after deployments",
          "prevention": "Zero-downtime deployment strategy; consumer health checks",
      },
  ]

  NEO4J_SEED_QUERIES = [
      # Halotel failure chain
      """
      MERGE (op:Operator {name: 'halotel', country: 'Tanzania'})
      MERGE (svc:Service {name: 'db_primary', type: 'database'})
      MERGE (cause:RootCause {name: 'connection_pool_exhaustion'})
      MERGE (symptom:Service {name: 'crbt_provisioning', type: 'application'})
      MERGE (fix:Fix {name: 'pool_size_increase', command: 'pgbouncer_reload_config --pool-size=150'})
      MERGE (op)-[:RUNS]->(svc)
      MERGE (svc)-[:CAUSES]->(cause)
      MERGE (cause)-[:MANIFESTS_IN]->(symptom)
      MERGE (cause)-[:RESOLVED_BY]->(fix)
      """,
      # Billing timeout chain
      """
      MERGE (billing:Service {name: 'billing_api', type: 'api'})
      MERGE (charging:Service {name: 'charging_platform', type: 'api'})
      MERGE (vas:Service {name: 'vas_subscription', type: 'application'})
      MERGE (timeout:RootCause {name: 'billing_api_timeout'})
      MERGE (billing)-[:DEPENDS_ON]->(charging)
      MERGE (billing)-[:CAUSES]->(timeout)
      MERGE (timeout)-[:MANIFESTS_IN]->(vas)
      """,
  ]
  