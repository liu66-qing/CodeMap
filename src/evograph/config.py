from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "GitGraph"
    app_env: str = "development"
    app_debug: bool = False
    app_host: str = "0.0.0.0"
    app_port: int = 8080
    secret_key: str = "change-me-in-production"

    # LLM (DeepSeek / OpenAI-compatible)
    llm_api_key: str = ""
    llm_base_url: str = "https://api.deepseek.com"
    llm_model_id: str = "deepseek-chat"

    # Embedding (DashScope / OpenAI-compatible)
    embed_model_type: str = "dashscope"
    embed_model_name: str = "text-embedding-v3"
    embed_api_key: str = ""
    embed_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    embed_dimensions: int = 1024

    # ASR (speech-to-text)
    asr_provider: str = "dashscope"  # dashscope | whisper_local
    asr_model: str = "paraformer-realtime-v2"

    # Web search (for active information completion)
    search_provider: str = "duckduckgo"  # duckduckgo | serpapi
    search_api_key: str = ""

    # Neo4j
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "evograph123"
    neo4j_database: str = "neo4j"

    # PostgreSQL
    database_url: str = "postgresql+asyncpg://evograph:evograph123@localhost:5432/evograph"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Qdrant
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""
    qdrant_collection: str = "pulsegraph_chunks"
    qdrant_vector_size: int = 1024
    qdrant_distance: str = "cosine"
    qdrant_timeout: int = 30

    # Celery
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # Feature flags
    douyin_enabled: bool = True
    active_search_enabled: bool = True
    max_search_rounds: int = 4
    max_content_per_query: int = 15

    @property
    def is_dev(self) -> bool:
        return self.app_env == "development"


settings = Settings()
