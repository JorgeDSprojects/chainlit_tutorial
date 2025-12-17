"""
Servicio para gestionar conversaciones y mensajes en la base de datos.
Implementa la Memoria a Largo Plazo (Fase 5.3).
"""
from sqlalchemy.future import select
from src.db.database import async_session
from src.db.models import Conversation, Message, User
from typing import Optional, List, Dict


async def create_conversation(user_id: int, title: str = "Nueva Conversación") -> Conversation:
    """
    Crea una nueva conversación vinculada a un usuario.
    
    Args:
        user_id: ID del usuario propietario de la conversación
        title: Título de la conversación (por defecto "Nueva Conversación")
        
    Returns:
        Conversation: La conversación creada
    """
    async with async_session() as session:
        # Verificar que el usuario existe
        result = await session.execute(select(User).filter(User.id == user_id))
        user = result.scalars().first()
        
        if not user:
            raise ValueError(f"Usuario con ID {user_id} no existe")
        
        # Crear nueva conversación
        conversation = Conversation(
            title=title,
            user_id=user_id
        )
        
        session.add(conversation)
        await session.commit()
        await session.refresh(conversation)
        
        return conversation


async def add_message(conversation_id: int, role: str, content: str) -> Message:
    """
    Añade un mensaje a una conversación existente.
    
    Args:
        conversation_id: ID de la conversación
        role: Rol del mensaje ("user", "assistant", "system")
        content: Contenido del mensaje
        
    Returns:
        Message: El mensaje creado
    """
    # Validar rol
    valid_roles = ["user", "assistant", "system"]
    if role not in valid_roles:
        raise ValueError(f"Rol inválido '{role}'. Debe ser uno de: {', '.join(valid_roles)}")
    
    async with async_session() as session:
        # Verificar que la conversación existe
        result = await session.execute(
            select(Conversation).filter(Conversation.id == conversation_id)
        )
        conversation = result.scalars().first()
        
        if not conversation:
            raise ValueError(f"Conversación con ID {conversation_id} no existe")
        
        # Crear mensaje
        message = Message(
            conversation_id=conversation_id,
            role=role,
            content=content
        )
        
        session.add(message)
        await session.commit()
        await session.refresh(message)
        
        return message


async def get_conversation_history(conversation_id: int, limit: Optional[int] = None) -> List[Dict[str, str]]:
    """
    Obtiene el historial de mensajes de una conversación.
    
    Args:
        conversation_id: ID de la conversación
        limit: Número máximo de mensajes a recuperar (None = todos)
        
    Returns:
        List[Dict[str, str]]: Lista de mensajes en formato [{"role": "user", "content": "..."}, ...]
    """
    async with async_session() as session:
        # Construir query
        query = select(Message).filter(
            Message.conversation_id == conversation_id
        ).order_by(Message.created_at)
        
        # Aplicar límite si se especifica
        if limit:
            query = query.limit(limit)
        
        result = await session.execute(query)
        messages = result.scalars().all()
        
        # Convertir a formato de historial
        history = [
            {
                "role": message.role,
                "content": message.content
            }
            for message in messages
        ]
        
        return history


async def delete_conversation(conversation_id: int) -> bool:
    """
    Elimina una conversación y todos sus mensajes.
    
    Args:
        conversation_id: ID de la conversación a eliminar
        
    Returns:
        bool: True si se eliminó correctamente, False si no se encontró
    """
    async with async_session() as session:
        result = await session.execute(
            select(Conversation).filter(Conversation.id == conversation_id)
        )
        conversation = result.scalars().first()
        
        if not conversation:
            return False
        
        # Eliminar conversación (los mensajes se eliminan en cascada)
        await session.delete(conversation)
        await session.commit()
        
        return True
