from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5433
    POSTGRES_USER: str = "studybuddy"
    POSTGRES_PASSWORD: str = "studybuddy"
    POSTGRES_DB: str = "studybuddy"
    
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    EMBED_MODEL: str = "bge-m3"
    EMBED_DIM: int = 1024
    EMBED_BATCH_SIZE: int = 16
    LLM_MODEL: str = "gemma:2b"
    
    TEMPORAL_HOST: str = "localhost:7233"
    TEMPORAL_NAMESPACE: str = "default"
    TEMPORAL_TASK_QUEUE: str = "ingest-queue"
    
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    UPLOAD_DIR: str = "./uploads"
    
    SENTRY_DSN: str = ""
    
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
    
    @property
    def sync_database_url(self) -> str:
        return f"postgresql+psycopg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        
    @property
    def async_database_url(self) -> str:
        return f"postgresql+psycopg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

settings = Settings()
