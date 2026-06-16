"""Application configuration via environment variables."""
  from pydantic_settings import BaseSettings
  from functools import lru_cache


  class Settings(BaseSettings):
      # Application
      app_name: str = "AI Telecom Ops Copilot"
      app_version: str = "1.0.0"
      debug: bool = False
      log_level: str = "INFO"

      # OpenAI
      openai_api_key: str = ""
      openai_model: str = "gpt-4o"
      openai_embedding_model: str = "text-embedding-3-small"

      # PostgreSQL
      database_url: str = "postgresql+asyncpg://telecom:telecom@localhost:5432/telecom_copilot"

      # Redis
      redis_url: str = "redis://localhost:6379/0"

      # Qdrant (vector store for RAG)
      qdrant_url: str = "http://localhost:6333"
      qdrant_collection: str = "telecom_incidents"

      # Neo4j (knowledge graph)
      neo4j_url: str = "bolt://localhost:7687"
      neo4j_user: str = "neo4j"
      neo4j_password: str = "telecom123"

      # Kafka
      kafka_bootstrap_servers: str = "localhost:9092"
      kafka_alert_topic: str = "telecom.alerts"

      # Safety
      require_human_approval_for_assisted: bool = True
      max_rca_hypotheses: int = 5
      min_confidence_threshold: float = 0.30

      # Predictive
      prediction_window_hours: int = 6
      prediction_interval_minutes: int = 15

      class Config:
          env_file = ".env"
          case_sensitive = False


  @lru_cache()
  def get_settings() -> Settings:
      return Settings()
  