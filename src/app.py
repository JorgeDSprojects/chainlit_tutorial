import chainlit as cl
from sqlalchemy.future import select
from src.db.database import async_session
from src.db.models import User
from src.auth.utils import verify_password
from src.services.llm_service import llm_service
from src.config import settings

# --- CALLBACK DE AUTENTICACIÓN ---
@cl.password_auth_callback
async def auth(username: str, password: str):
    async with async_session() as session:
        result = await session.execute(select(User).filter(User.email == username))
        user_db = result.scalars().first()
        
        if user_db and verify_password(password, user_db.hashed_password):
            return cl.User(identifier=username, metadata={"id": user_db.id})
        return None

@cl.on_chat_start
async def start():
    # SOLUCIÓN ERROR: Verificar si el usuario existe antes de usarlo
    user = cl.user_session.get("user")
    
    if user:
        await cl.Message(f"Hola {user.identifier}, ¡bienvenido de nuevo!").send()
    else:
        # Si se recargó el servidor, la sesión puede perderse momentáneamente en desarrollo
        await cl.Message("Sesión reiniciada. Si tienes problemas, recarga la página.").send()

    # Inicializar historial de mensajes para memoria a corto plazo
    cl.user_session.set("message_history", [])

    # Configuración del chat (Widgets)
    chat_settings = await cl.ChatSettings(
        [
            cl.input_widget.Select(
                id="ModelProvider",
                label="Proveedor de IA",
                values=["ollama", "openai", "openrouter"],
                initial_index=0
            ),
            cl.input_widget.TextInput(
                id="ModelName",
                label="Nombre del Modelo (Opcional)",
                initial="llama2",
                description="Ej: gpt-4, llama3, mistralai/mistral-7b-instruct"
            )
        ]
    ).send()

@cl.on_message
async def main(message: cl.Message):
    # Obtener configuración del chat
    chat_settings = cl.user_session.get("chat_settings")
    provider = "ollama"
    model_name = "llama2"
    
    if chat_settings:
        provider = chat_settings.get("ModelProvider", "ollama")
        model_name = chat_settings.get("ModelName", None)

    # Obtener historial de mensajes
    message_history = cl.user_session.get("message_history", [])
    
    # Crear mensaje de respuesta
    msg = cl.Message(content="")
    await msg.send()

    # Generar respuesta con historial
    full_response = ""
    async for token in llm_service.stream_response(
        message=message.content, 
        provider=provider, 
        specific_model=model_name,
        history=message_history
    ):
        full_response += token
        await msg.stream_token(token)
    
    await msg.update()
    
    # Actualizar historial: añadir mensaje del usuario y respuesta del asistente
    message_history.append({"role": "user", "content": message.content})
    message_history.append({"role": "assistant", "content": full_response})
    
    # Truncar historial al límite configurado (mantener los últimos MAX_CONTEXT_MESSAGES)
    if len(message_history) > settings.MAX_CONTEXT_MESSAGES:
        message_history = message_history[-settings.MAX_CONTEXT_MESSAGES:]
    
    # Guardar historial actualizado en la sesión
    cl.user_session.set("message_history", message_history)

@cl.on_settings_update
async def setup_agent(settings):
    cl.user_session.set("chat_settings", settings)
    await cl.Message(content=f"✅ Proveedor cambiado a: {settings['ModelProvider']}").send()
