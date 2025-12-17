from openai import AsyncOpenAI
from src.config import settings
import aiohttp
from typing import List, Dict

class LLMService:
    def __init__(self):
        # Inicializamos los clientes. 
        # Nota: En producción, podrías usar Singleton o Inyección de Dependencias.
        pass

    def _get_client_and_model(self, provider: str):
        """
        Devuelve el cliente configurado y el nombre del modelo por defecto 
        según el proveedor seleccionado.
        """
        if provider == "ollama":
            # Ollama corre localmente (o en Docker mapeado a localhost)
            return AsyncOpenAI(
                base_url=settings.OLLAMA_BASE_URL, 
                api_key="ollama" # Requerido por la librería, pero ignorado por Ollama
            ), "llama2" # Asegúrate de haber hecho 'ollama pull llama3' en tu contenedor
            
        elif provider == "openrouter":
            # OpenRouter
            return AsyncOpenAI(
                base_url="[https://openrouter.ai/api/v1](https://openrouter.ai/api/v1)",
                api_key=settings.OPENROUTER_API_KEY
            ), "openai/gpt-3.5-turbo" # Modelo default de OpenRouter
            
        elif provider == "openai":
            # OpenAI Oficial
            return AsyncOpenAI(
                api_key=settings.OPENAI_API_KEY
            ), "gpt-3.5-turbo"
            
        else:
            raise ValueError(f"Proveedor desconocido: {provider}")

    async def get_ollama_models(self) -> List[str]:
        """
        Fetch available models from Ollama API.
        
        Returns:
            List of model names available in Ollama
        """
        try:
            # Extract base URL without /v1 suffix
            base_url = settings.OLLAMA_BASE_URL.replace("/v1", "")
            url = f"{base_url}/api/tags"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        models = data.get("models", [])
                        return [model.get("name", "") for model in models if model.get("name")]
                    else:
                        return ["llama2"]  # Fallback default
        except Exception as e:
            print(f"Error fetching Ollama models: {str(e)}")
            return ["llama2"]  # Fallback default

    async def stream_response(self, message: str, provider: str, specific_model: str = None, history: list[dict] = None, temperature: float = 0.7):
        """
        Genera una respuesta en streaming.
        
        Args:
            message: El mensaje actual del usuario
            provider: Proveedor de LLM (ollama, openai, openrouter)
            specific_model: Modelo específico a usar (opcional)
            history: Historial de mensajes previos (opcional)
            temperature: Temperature for response generation (0.0-1.0)
        """
        client, default_model = self._get_client_and_model(provider)
        
        # Si la UI nos manda un modelo específico, lo usamos, si no, el default
        model = specific_model if specific_model else default_model

        # Construir mensajes con historial
        messages = [
            {"role": "system", "content": "Eres un asistente útil y conciso."}
        ]
        
        # Añadir historial si existe
        if history:
            messages.extend(history)
        
        # Añadir el mensaje actual
        messages.append({"role": "user", "content": message})

        try:
            stream = await client.chat.completions.create(
                model=model,
                messages=messages,
                stream=True,
                temperature=temperature
            )
            
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            yield f"\n\n**Error al conectar con {provider}:** {str(e)}"

# Instancia global para usar en app.py
llm_service = LLMService()