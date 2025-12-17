from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_NAME: str = "ChatMultiModel"
    DEBUG: bool = True
    
    # LLM Keys (De la Fase 2)
    OPENAI_API_KEY: str = "sk-..."
    OPENROUTER_API_KEY: str = "sk-..."
    OLLAMA_BASE_URL: str = "http://localhost:11434/v1"

    # AÑADIDO: Clave de autenticación para Chainlit (DEBE EXISTIR AQUÍ)
    CHAINLIT_AUTH_SECRET: str 
    
    # Fase 5: Sistema de Memoria - Configuración de Límites
    # Maximum number of individual messages (not conversation turns) to keep in context
    # Each conversation turn = 2 messages (user + assistant)
    MAX_CONTEXT_MESSAGES: int = 15
    VISION_MODEL: str = "llama3.2-vision"
    PDF_CHUNK_SIZE: int = 2000
    PDF_CHUNK_OVERLAP: int = 200
    MAX_PDF_SIZE_MB: int = 10
    MAX_IMAGE_SIZE_MB: int = 5

    class Config:
        env_file = ".env"

settings = Settings()