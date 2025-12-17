import chainlit as cl
from chainlit.data import get_data_layer
from sqlalchemy.future import select
from src.db.database import async_session
from src.db.models import User, Conversation
from src.auth.utils import verify_password
from src.services.llm_service import llm_service
from src.services.chainlit_data_layer import ChainlitDataLayer
from src.config import settings

# Configure Chainlit data layer for thread persistence
cl.data._data_layer = ChainlitDataLayer()

# --- CALLBACK DE AUTENTICACIÓN ---
@cl.password_auth_callback
async def auth(username: str, password: str):
    async with async_session() as session:
        result = await session.execute(select(User).filter(User.email == username))
        user_db = result.scalars().first()
        
        if user_db and verify_password(password, user_db.hashed_password):
            return cl.User(identifier=username, metadata={"id": user_db.id})
        return None

@cl.on_chat_resume
async def on_chat_resume(thread: cl.ThreadDict):
    """Resume a previous conversation when user clicks on it in the sidebar"""
    # Get thread data from data layer
    thread_id = thread.get("id")
    
    if not thread_id:
        return
    
    # Store thread_id in session
    cl.user_session.set("thread_id", thread_id)
    cl.user_session.set("conversation_id", int(thread_id))
    
    # Load message history from the thread
    steps = thread.get("steps", [])
    message_history = []
    
    # Reconstruct message history from steps
    for step in steps:
        step_type = step.get("type", "")
        if step_type == "user_message":
            content = step.get("input", "")
            if content:
                message_history.append({"role": "user", "content": content})
        elif step_type == "assistant_message":
            content = step.get("output", "")
            if content:
                message_history.append({"role": "assistant", "content": content})
    
    # Store in user session
    cl.user_session.set("message_history", message_history)
    
    # Display previous messages to the user
    for step in steps:
        step_type = step.get("type", "")
        if step_type == "user_message":
            content = step.get("input", "")
            if content:
                await cl.Message(
                    author="Usuario",
                    content=content,
                    type="user_message"
                ).send()
        elif step_type == "assistant_message":
            content = step.get("output", "")
            if content:
                await cl.Message(
                    author="Assistant",
                    content=content,
                    type="assistant_message"
                ).send()

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
    
    # Create a new conversation in the database
    if user:
        async with async_session() as session:
            # Get user from database
            result = await session.execute(select(User).filter(User.email == user.identifier))
            db_user = result.scalars().first()
            
            if db_user:
                # Create new conversation
                conversation = Conversation(
                    title="Nueva Conversación",
                    user_id=db_user.id
                )
                session.add(conversation)
                await session.commit()
                await session.refresh(conversation)
                
                # Store conversation ID in user session
                cl.user_session.set("conversation_id", conversation.id)
                
                # Set the thread_id for Chainlit
                cl.user_session.set("thread_id", str(conversation.id))

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
    
    # Get thread_id for persistence
    thread_id = cl.user_session.get("thread_id")
    
    # Create user message step for persistence
    if thread_id:
        user_step = cl.Step(
            name="user",
            type="user_message",
            thread_id=thread_id
        )
        user_step.input = message.content
        user_step.output = message.content
        await user_step.send()
    
    # Crear mensaje de respuesta
    msg = cl.Message(content="")
    
    # Create assistant step for persistence
    if thread_id:
        assistant_step = cl.Step(
            name="assistant",
            type="assistant_message",
            thread_id=thread_id
        )
        await assistant_step.send()
    
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
    
    # Update assistant step with response
    if thread_id:
        assistant_step.output = full_response
        await assistant_step.update()
    
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

@cl.on_settings_update
async def setup_agent(settings):
    cl.user_session.set("chat_settings", settings)
    await cl.Message(content=f"✅ Proveedor cambiado a: {settings['ModelProvider']}").send()
