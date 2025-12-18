"""
Chainlit Data Layer implementation for persistence.
This connects Chainlit's conversation history feature with our existing database.
"""
from typing import Optional, Dict, List
from datetime import datetime
import asyncio
from chainlit.data import BaseDataLayer
from chainlit.types import (
    ThreadDict,
    Pagination,
    ThreadFilter,
    PaginatedResponse,
    PageInfo,
)
from chainlit.step import StepDict
from chainlit.user import PersistedUser
from sqlalchemy.future import select
from sqlalchemy import desc, func
from src.db.database import async_session
from src.db.models import Conversation, Message, User


class ChainlitDataLayer(BaseDataLayer):
    """
    Custom data layer that integrates Chainlit with our SQLite database.
    Implements conversation history and thread management.
    """

    def __init__(self):
        # Map Chainlit step IDs -> message DB IDs to support streaming updates
        # Protected by asyncio lock for thread-safe concurrent access in async context
        self._step_message_map: Dict[str, int] = {}
        self._map_lock = None  # Initialized lazily in async context
    
    def _get_lock(self):
        """Get or create the asyncio lock in the current event loop."""
        if self._map_lock is None:
            import asyncio
            self._map_lock = asyncio.Lock()
        return self._map_lock
    
    async def get_user(self, identifier: str) -> Optional[PersistedUser]:
        """Get user by identifier (email) and return Chainlit PersistedUser."""
        async with async_session() as session:
            result = await session.execute(select(User).filter(User.email == identifier))
            user = result.scalars().first()
            if not user:
                return None

            created_at = (
                user.created_at.isoformat() if user.created_at else datetime.utcnow().isoformat()
            )

            return PersistedUser(
                id=str(user.id),
                identifier=user.email,
                display_name=user.email,
                metadata={"id": user.id},
                createdAt=created_at,
            )
    
    async def create_user(self, user):
        """Create a new user - not implemented as we handle this via auth."""
        return None
    
    async def _get_conversation_by_thread(
        self,
        session,
        thread_id: str,
    ) -> Optional[Conversation]:
        """Utility that fetches a conversation by thread_id or falls back to numeric ID."""
        if not thread_id:
            return None

        result = await session.execute(
            select(Conversation).filter(Conversation.thread_id == thread_id)
        )
        conversation = result.scalars().first()

        if conversation:
            return conversation

        # Backwards compatibility: allow selecting by numeric database ID when no thread_id,
        # so historical chats created antes de la migración siguen funcionando.
        try:
            numeric_id = int(thread_id)
        except (TypeError, ValueError):
            return None

        result = await session.execute(
            select(Conversation).filter(Conversation.id == numeric_id)
        )
        return result.scalars().first()

    async def get_thread(self, thread_id: str) -> Optional[ThreadDict]:
        """
        Retrieve a specific thread (conversation) with all its messages.
        
        Args:
            thread_id: The Chainlit thread ID (UUID string)
            
        Returns:
            ThreadDict with conversation details and all messages as steps
        """
        async with async_session() as session:
            conversation = await self._get_conversation_by_thread(session, thread_id)
            
            if not conversation:
                return None

            user_identifier = None
            user_result = await session.execute(
                select(User).filter(User.id == conversation.user_id)
            )
            if user_db := user_result.scalars().first():
                user_identifier = user_db.email
            
            # Get all messages for this conversation
            messages_result = await session.execute(
                select(Message)
                .filter(Message.conversation_id == conversation.id)
                .order_by(Message.created_at)
            )
            messages = messages_result.scalars().all()
            
            # Convert messages to StepDict format
            steps = []
            for msg in messages:
                step_type = "user_message" if msg.role == "user" else "assistant_message"
                content = msg.content or ""
                # Chainlit usa "output" para renderizar tanto mensajes de usuario como del asistente
                steps.append({
                    "id": str(msg.id),
                    "name": msg.role,
                    "type": step_type,
                    "threadId": thread_id,
                    "parentId": None,
                    "streaming": False,
                    "input": content if msg.role == "user" else "",
                    "output": content,
                    "createdAt": msg.created_at.isoformat() if msg.created_at else None,
                    "metadata": {},
                    "tags": []
                })
            
            # Return ThreadDict
            return {
                "id": conversation.thread_id or thread_id,
                "name": conversation.title,
                "createdAt": conversation.created_at.isoformat() if conversation.created_at else None,
                "userId": str(conversation.user_id),
                "userIdentifier": user_identifier,
                "steps": steps,
                "metadata": {},
                "tags": []
            }
    
    async def list_threads(
        self, 
        pagination: Pagination, 
        filters: ThreadFilter
    ) -> PaginatedResponse[ThreadDict]:
        """
        List all threads (conversations) for a user with pagination.
        
        Args:
            pagination: Pagination parameters (page, pageSize)
            filters: Filter parameters (userId, etc.)
            
        Returns:
            PaginatedResponse with list of threads
        """
        async with async_session() as session:
            # Build query
            query = select(Conversation)
            
            # Filter by user if specified
            if filters.userId:
                query = query.filter(Conversation.user_id == int(filters.userId))
            
            # Order by created date descending (newest first)
            query = query.order_by(desc(Conversation.created_at))
            
            # Apply pagination (cursor = offset, first = page size)
            page_size = pagination.first or 20
            try:
                offset = int(pagination.cursor) if pagination.cursor else 0
            except ValueError:
                offset = 0
            query = query.offset(offset).limit(page_size)
            
            # Execute query
            result = await session.execute(query)
            conversations = result.scalars().all()
            
            # Get total count for pagination (efficient count query)
            count_query = select(func.count(Conversation.id))
            if filters.userId:
                count_query = count_query.filter(Conversation.user_id == int(filters.userId))
            count_result = await session.execute(count_query)
            total = count_result.scalar() or 0
            
            # Prepare map of user identifiers to avoid repeated queries
            user_ids = {conv.user_id for conv in conversations if conv.user_id}
            user_map: Dict[int, str] = {}
            if user_ids:
                users_result = await session.execute(select(User).filter(User.id.in_(user_ids)))
                for user in users_result.scalars().all():
                    user_map[user.id] = user.email

            # Convert to ThreadDict format (without loading all messages)
            threads = []
            for conv in conversations:
                # Use thread_id if available, otherwise fall back to str(id)
                thread_id = conv.thread_id if conv.thread_id else str(conv.id)
                user_identifier = user_map.get(conv.user_id)
                threads.append({
                    "id": thread_id,
                    "name": conv.title,
                    "createdAt": conv.created_at.isoformat() if conv.created_at else None,
                    "userId": str(conv.user_id),
                    "userIdentifier": user_identifier,
                    "steps": [],  # Don't load all steps in list view
                    "metadata": {},
                    "tags": []
                })
            
            next_offset = offset + len(threads)
            page_info = PageInfo(
                hasNextPage=next_offset < total,
                startCursor=str(offset) if threads else None,
                endCursor=str(next_offset) if threads else None,
            )
            return PaginatedResponse(data=threads, pageInfo=page_info)
    
    async def delete_thread(self, thread_id: str):
        """
        Delete a thread (conversation) and all its messages.
        
        Args:
            thread_id: The Chainlit thread ID to delete
        """
        async with async_session() as session:
            conversation = await self._get_conversation_by_thread(session, thread_id)
            
            if conversation:
                await session.delete(conversation)
                await session.commit()
    
    async def create_step(self, step_dict: StepDict):
        """
        Create a new step (message) in a thread.
        
        Args:
            step_dict: Step data containing message information
        """
        async with async_session() as session:
            thread_id = step_dict.get("threadId")
            if not thread_id:
                return
            
            conversation = await self._get_conversation_by_thread(session, thread_id)
            
            if not conversation:
                # Thread doesn't exist yet, skip for now
                # It will be created when the conversation starts
                return
            
            # Determine role from step type
            step_type = step_dict.get("type", "")
            if "user" in step_type:
                role = "user"
            elif "assistant" in step_type:
                role = "assistant"
            else:
                role = "system"

            # Chainlit envía el texto principal en "output" para ambos roles.
            # Usamos "input" solo como respaldo.
            content = step_dict.get("output") or step_dict.get("input", "")
            
            # Allow assistant placeholders (empty content) so we can update after streaming
            if not content and role != "assistant":
                return
            
            # Create message
            message = Message(
                conversation_id=conversation.id,
                role=role,
                content=content
            )
            
            session.add(message)
            await session.flush()

            # Track message id for future updates (thread-safe)
            step_id = step_dict.get("id")
            if step_id and message.id:
                async with self._get_lock():
                    self._step_message_map[step_id] = message.id

            await session.commit()
    
    async def update_step(self, step_dict: StepDict):
        """Update assistant messages after streaming completes."""
        step_id = step_dict.get("id")
        if not step_id:
            return

        content = step_dict.get("output") or step_dict.get("input", "")
        if not content:
            return

        step_type = step_dict.get("type", "")
        if "assistant" in step_type:
            role = "assistant"
        elif "user" in step_type:
            role = "user"
        else:
            role = "system"

        async with async_session() as session:
            message = None

            # Check map for step_id (thread-safe)
            async with self._get_lock():
                message_id = self._step_message_map.get(step_id)
            
            if message_id:
                result = await session.execute(
                    select(Message).filter(Message.id == message_id)
                )
                message = result.scalars().first()

            if not message:
                # Fallback: locate the most recent message for this conversation and role
                thread_id = step_dict.get("threadId")
                conversation = await self._get_conversation_by_thread(session, thread_id)
                if not conversation:
                    return

                result = await session.execute(
                    select(Message)
                    .filter(
                        Message.conversation_id == conversation.id,
                        Message.role == role,
                    )
                    .order_by(desc(Message.created_at))
                    .limit(1)
                )
                message = result.scalars().first()

            if not message:
                return

            message.content = content
            await session.commit()
    
    async def delete_step(self, step_id: str):
        """Delete a step - not implemented."""
        pass
    
    async def update_thread(
        self,
        thread_id: str,
        name: Optional[str] = None,
        user_id: Optional[str] = None,
        metadata: Optional[Dict] = None,
        tags: Optional[List[str]] = None
    ):
        """
        Update thread metadata.
        
        Args:
            thread_id: The Chainlit thread ID
            name: New name/title for the thread
            user_id: New user ID (not used)
            metadata: Additional metadata (not used)
            tags: Tags for the thread (not used)
        """
        async with async_session() as session:
            conversation = await self._get_conversation_by_thread(session, thread_id)
            
            if conversation and name:
                conversation.title = name
                await session.commit()
    
    async def get_thread_author(self, thread_id: str) -> str:
        """Get the author (user identifier) of a thread."""
        async with async_session() as session:
            conversation = await self._get_conversation_by_thread(session, thread_id)
            
            if conversation:
                user_result = await session.execute(
                    select(User).filter(User.id == conversation.user_id)
                )
                user = user_result.scalars().first()
                if user:
                    return user.email
            return ""
    
    # Implement remaining abstract methods with minimal functionality
    
    def build_debug_url(self) -> str:
        """Build debug URL - not implemented."""
        return ""
    
    async def close(self) -> None:
        """Close data layer connections - not needed for our implementation."""
        pass
    
    async def create_element(self, element):
        """Create an element (file/attachment) - not implemented."""
        pass
    
    async def delete_element(self, element_id: str, thread_id: Optional[str] = None):
        """Delete an element - not implemented."""
        pass
    
    async def get_element(self, thread_id: str, element_id: str):
        """Get an element - not implemented."""
        return None
    
    async def delete_feedback(self, feedback_id: str) -> bool:
        """Delete feedback - not implemented."""
        return False
    
    async def upsert_feedback(self, feedback) -> str:
        """Create or update feedback - not implemented."""
        return ""
