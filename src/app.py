import chainlit as cl
from sqlalchemy.future import select
from src.db.database import async_session
from src.db.models import User
from src.auth.utils import verify_password
from src.services.llm_service import llm_service
from src.services.conversation_service import create_conversation, add_message, get_conversation_history
from src.config import settings
from src.services.chainlit_data_layer import ChainlitDataLayer
from src.services.user_settings_service import get_or_create_settings, save_settings

# Register data layer for thread/history support
cl.data_layer = ChainlitDataLayer()

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
    user_id = None
    user_settings_data = None
    
    if user:
        await cl.Message(f"Hola {user.identifier}, ¡bienvenido de nuevo!").send()
        
        # Crear nueva conversación vinculada al usuario (Memoria a Largo Plazo)
        try:
            user_id = user.metadata.get("id")
            if user_id is None:
                raise ValueError("El usuario no tiene un ID válido en metadata")
            conversation = await create_conversation(user_id=user_id, title="Nueva Conversación")
            cl.user_session.set("conversation_id", conversation.id)
            
            # Load user settings
            user_settings_data = await get_or_create_settings(user_id)
        except Exception as e:
            await cl.Message(f"⚠️ Error al crear conversación: {str(e)}").send()
    else:
        # Si se recargó el servidor, la sesión puede perderse momentáneamente en desarrollo
        await cl.Message("Sesión reiniciada. Si tienes problemas, recarga la página.").send()

    # Inicializar historial de mensajes para memoria a corto plazo
    cl.user_session.set("message_history", [])

    # Get available Ollama models dynamically
    ollama_models = await llm_service.get_ollama_models()
    
    # Get initial values from user settings or use defaults
    initial_model = user_settings_data.get("default_model", "llama2") if user_settings_data else "llama2"
    initial_temperature = user_settings_data.get("temperature", 0.7) if user_settings_data else 0.7
    
    # Find the index of the initial model in the list
    initial_model_index = 0
    if initial_model in ollama_models:
        initial_model_index = ollama_models.index(initial_model)
    
    # Configuración del chat (Widgets) with dynamic models and user settings
    chat_settings = await cl.ChatSettings(
        [
            cl.input_widget.Select(
                id="ModelProvider",
                label="Proveedor de IA",
                values=["ollama", "openai", "openrouter"],
                initial_index=0
            ),
            cl.input_widget.Select(
                id="ModelName",
                label="Modelo",
                values=ollama_models,
                initial_index=initial_model_index
            ),
            cl.input_widget.Slider(
                id="Temperature",
                label="Temperatura",
                initial=initial_temperature,
                min=0.0,
                max=1.0,
                step=0.1,
                description="Controla la creatividad: 0.0 = preciso, 1.0 = creativo"
            )
        ]
    ).send()

@cl.on_chat_resume
async def on_chat_resume(thread: dict):
    """
    Called when a user resumes a previous conversation from the history sidebar.
    Loads the conversation history from the database and repopulates the session.
    """
    # Get thread/conversation ID
    thread_id = thread.get("id")
    if not thread_id:
        await cl.Message("⚠️ No se pudo cargar el historial: ID de conversación no válido").send()
        return
    
    # Set the conversation_id in session
    cl.user_session.set("conversation_id", int(thread_id))
    
    # Load conversation history from database
    try:
        history = await get_conversation_history(conversation_id=int(thread_id))
        
        # Populate the message_history in session
        cl.user_session.set("message_history", history)
        
        # Display previous messages to user
        if history:
            # Group messages by pairs (user + assistant)
            for i in range(0, len(history), 2):
                user_msg = history[i] if i < len(history) else None
                assistant_msg = history[i + 1] if i + 1 < len(history) else None
                
                if user_msg and user_msg.get("role") == "user":
                    await cl.Message(
                        content=user_msg.get("content", ""),
                        author="user"
                    ).send()
                
                if assistant_msg and assistant_msg.get("role") == "assistant":
                    await cl.Message(
                        content=assistant_msg.get("content", ""),
                        author="assistant"
                    ).send()
            
            await cl.Message(f"✅ Conversación cargada con {len(history)} mensajes. Puedes continuar donde lo dejaste.").send()
        else:
            await cl.Message("📝 Conversación vacía. Comienza a chatear.").send()
            
    except Exception as e:
        await cl.Message(f"⚠️ Error al cargar el historial: {str(e)}").send()
        # Initialize empty history on error
        cl.user_session.set("message_history", [])

@cl.on_message
async def main(message: cl.Message):
    # Obtener configuración del chat
    chat_settings = cl.user_session.get("chat_settings")
    provider = "ollama"
    model_name = "llama2"
    temperature = 0.7
    
    if chat_settings:
        provider = chat_settings.get("ModelProvider", "ollama")
        model_name = chat_settings.get("ModelName", "llama2")
        temperature = chat_settings.get("Temperature", 0.7)

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
        history=message_history,
        temperature=temperature
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
    
    # Guardar mensajes en la base de datos (Memoria a Largo Plazo)
    if conversation_id:
        try:
            await add_message(conversation_id=conversation_id, role="user", content=message.content)
            await add_message(conversation_id=conversation_id, role="assistant", content=full_response)
        except Exception as e:
            # Loguear error pero no interrumpir el flujo de conversación
            print(f"Error guardando mensajes en BD: {str(e)}")

@cl.on_settings_update
async def setup_agent(settings_dict):
    # Update session settings
    cl.user_session.set("chat_settings", settings_dict)
    
    # Persist settings to database if user is logged in
    user = cl.user_session.get("user")
    if user:
        try:
            user_id = user.metadata.get("id")
            if user_id:
                await save_settings(
                    user_id=user_id,
                    default_model=settings_dict.get("ModelName"),
                    temperature=settings_dict.get("Temperature")
                )
                await cl.Message(content=f"✅ Configuración guardada: {settings_dict.get('ModelName')} a temperatura {settings_dict.get('Temperature')}").send()
            else:
                await cl.Message(content=f"✅ Configuración actualizada (no guardada - sin user_id)").send()
        except Exception as e:
            await cl.Message(content=f"⚠️ Error al guardar configuración: {str(e)}").send()
    else:
        await cl.Message(content=f"✅ Configuración actualizada para esta sesión").send()
