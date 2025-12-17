import chainlit as cl
from sqlalchemy.future import select
from src.db.database import async_session
from src.db.models import User
from src.auth.utils import verify_password
from src.services.llm_service import llm_service
from src.services.conversation_service import create_conversation, add_message
from src.services.chainlit_data_layer import ChainlitDataLayer
from src.config import settings

# Initialize and register the custom data layer with Chainlit
@cl.data_layer
def configure_data_layer():
    return ChainlitDataLayer()

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
    # Get the current thread_id from Chainlit's session
    from chainlit.context import context
    thread_id = context.session.thread_id
    thread_id_to_resume = context.session.thread_id_to_resume
    
    # SOLUCIÓN ERROR: Verificar si el usuario existe antes de usarlo
    user = cl.user_session.get("user")
    user_id = None
    user_identifier = None

    if user:
        # Chainlit guarda al usuario como cl.User durante la sesión inicial, pero al reanudar
        # puede serializarlo a dict. Soportamos ambos formatos.
        if isinstance(user, cl.User):
            user_identifier = user.identifier
            user_id = (user.metadata or {}).get("id")
        elif isinstance(user, dict):
            user_identifier = user.get("identifier")
            metadata = user.get("metadata") or {}
            user_id = metadata.get("id")
        else:
            user_id = None
            user_identifier = None
        
        if thread_id_to_resume:
            # User clicked on an old conversation - load it from database
            name = user_identifier or "usuario"
            await cl.Message(f"Hola {name}, continuemos con esta conversación.").send()
            # The data layer will automatically load the conversation history
            # No need to do anything else - Chainlit handles it
        else:
            # New conversation - create it in the database with Chainlit's thread_id
            name = user_identifier or "usuario"
            await cl.Message(f"Hola {name}, ¡bienvenido de nuevo!").send()
            
            try:
                if user_id is None:
                    raise ValueError("El usuario no tiene un ID válido en metadata")
                    
                # Create new conversation with Chainlit's thread_id
                conversation = await create_conversation(
                    user_id=user_id, 
                    title="Nueva Conversación",
                    thread_id=thread_id
                )
                cl.user_session.set("conversation_id", conversation.id)
            except Exception as e:
                await cl.Message(f"⚠️ Error al crear conversación: {str(e)}").send()
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
    
    # Obtener conversation_id para guardar en BD
    conversation_id = cl.user_session.get("conversation_id")
    
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
    
    # Truncar historial al límite configurado (mantener los últimos MAX_CONTEXT_MESSAGES mensajes individuales)
    # Nota: MAX_CONTEXT_MESSAGES cuenta mensajes individuales, no pares de conversación
    # Por ejemplo, 15 mensajes = ~7 turnos de conversación completos
    if len(message_history) > settings.MAX_CONTEXT_MESSAGES:
        message_history = message_history[-settings.MAX_CONTEXT_MESSAGES:]
    
    # Guardar historial actualizado en la sesión
    cl.user_session.set("message_history", message_history)
    
    # NOTE: Messages are now automatically saved by the Chainlit Data Layer
    # The data layer's create_step() method is called automatically when messages are sent
    # No need for manual message saving here

@cl.on_settings_update
async def setup_agent(settings):
    cl.user_session.set("chat_settings", settings)
    await cl.Message(content=f"✅ Proveedor cambiado a: {settings['ModelProvider']}").send()
