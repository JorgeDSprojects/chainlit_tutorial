"""
Chainlit Data Layer Implementation
Implements BaseDataLayer to integrate with Chainlit's thread/history system.
"""
from typing import Optional, Dict, List
from chainlit.data import BaseDataLayer
from chainlit.element import Element
from chainlit.step import StepDict
from chainlit.types import ThreadDict, Pagination
from sqlalchemy.future import select
from sqlalchemy import desc
from src.db.database import async_session
from src.db.models import Conversation, Message, User


class ChainlitDataLayer(BaseDataLayer):
    """
    Data layer that connects Chainlit's thread system with our database.
    Allows users to view conversation history and resume previous chats.
    """

    async def get_user(self, identifier: str) -> Optional[Dict]:
        """
        Retrieve user information by identifier (email).
        
        Args:
            identifier: User's email address
            
        Returns:
            User dict or None if not found
        """
        async with async_session() as session:
            result = await session.execute(
                select(User).filter(User.email == identifier)
            )
            user = result.scalars().first()
            
            if user:
                return {
                    "id": str(user.id),
                    "identifier": user.email,
                    "metadata": {"id": user.id}
                }
            return None

    async def create_user(self, user: Dict) -> Optional[Dict]:
        """
        Create a new user (not implemented - users are created through auth system).
        """
        return None

    async def get_thread(self, thread_id: str) -> Optional[ThreadDict]:
        """
        Get a specific thread (conversation) with its metadata and steps (messages).
        
        Args:
            thread_id: Conversation ID
            
        Returns:
            ThreadDict with conversation data and messages
        """
        async with async_session() as session:
            # Get conversation with messages
            result = await session.execute(
                select(Conversation).filter(Conversation.id == int(thread_id))
            )
            conversation = result.scalars().first()
            
            if not conversation:
                return None
            
            # Get messages for this conversation
            messages_result = await session.execute(
                select(Message)
                .filter(Message.conversation_id == conversation.id)
                .order_by(Message.created_at)
            )
            messages = messages_result.scalars().all()
            
            # Convert messages to steps format
            steps = []
            for msg in messages:
                step: StepDict = {
                    "id": str(msg.id),
                    "name": msg.role,
                    "type": "user_message" if msg.role == "user" else "assistant_message",
                    "output": msg.content,
                    "createdAt": msg.created_at.isoformat() if msg.created_at else None,
                }
                steps.append(step)
            
            thread: ThreadDict = {
                "id": str(conversation.id),
                "name": conversation.title,
                "userId": str(conversation.user_id),
                "createdAt": conversation.created_at.isoformat() if conversation.created_at else None,
                "steps": steps,
                "metadata": {}
            }
            
            return thread

    async def create_thread(
        self,
        user_id: str,
        name: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> ThreadDict:
        """
        Create a new thread (conversation).
        
        Args:
            user_id: User ID
            name: Thread name/title
            metadata: Additional metadata
            
        Returns:
            Created thread dict
        """
        async with async_session() as session:
            conversation = Conversation(
                title=name or "Nueva Conversación",
                user_id=int(user_id)
            )
            session.add(conversation)
            await session.commit()
            await session.refresh(conversation)
            
            thread: ThreadDict = {
                "id": str(conversation.id),
                "name": conversation.title,
                "userId": str(conversation.user_id),
                "createdAt": conversation.created_at.isoformat() if conversation.created_at else None,
                "steps": [],
                "metadata": metadata or {}
            }
            
            return thread

    async def update_thread(
        self,
        thread_id: str,
        name: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> None:
        """
        Update thread metadata.
        
        Args:
            thread_id: Conversation ID
            name: New name/title
            metadata: Updated metadata
        """
        async with async_session() as session:
            result = await session.execute(
                select(Conversation).filter(Conversation.id == int(thread_id))
            )
            conversation = result.scalars().first()
            
            if conversation:
                if name:
                    conversation.title = name
                await session.commit()

    async def delete_thread(self, thread_id: str) -> None:
        """
        Delete a thread and all its messages.
        
        Args:
            thread_id: Conversation ID to delete
        """
        async with async_session() as session:
            result = await session.execute(
                select(Conversation).filter(Conversation.id == int(thread_id))
            )
            conversation = result.scalars().first()
            
            if conversation:
                session.delete(conversation)
                await session.commit()

    async def list_threads(
        self,
        user_id: str,
        pagination: Pagination,
        filters: Optional[Dict] = None
    ) -> List[ThreadDict]:
        """
        List all threads for a user with pagination.
        
        Args:
            user_id: User ID
            pagination: Pagination parameters
            filters: Optional filters
            
        Returns:
            List of thread dicts
        """
        async with async_session() as session:
            # Build query
            query = select(Conversation).filter(
                Conversation.user_id == int(user_id)
            ).order_by(desc(Conversation.created_at))
            
            # Apply pagination
            if pagination.first:
                query = query.limit(pagination.first)
            
            result = await session.execute(query)
            conversations = result.scalars().all()
            
            # Convert to thread dicts
            threads = []
            for conv in conversations:
                thread: ThreadDict = {
                    "id": str(conv.id),
                    "name": conv.title,
                    "userId": str(conv.user_id),
                    "createdAt": conv.created_at.isoformat() if conv.created_at else None,
                    "steps": [],  # Don't load all steps for list view
                    "metadata": {}
                }
                threads.append(thread)
            
            return threads

    async def create_step(self, step_dict: StepDict) -> None:
        """
        Create a step (message) in a thread.
        
        Args:
            step_dict: Step data including thread_id and content
        """
        thread_id = step_dict.get("threadId")
        if not thread_id:
            return
        
        # Determine role from step type
        step_type = step_dict.get("type", "")
        if step_type == "user_message":
            role = "user"
        elif step_type in ["assistant_message", "run"]:
            role = "assistant"
        else:
            role = "system"
        
        # Get content
        content = step_dict.get("output", "")
        
        async with async_session() as session:
            message = Message(
                conversation_id=int(thread_id),
                role=role,
                content=content
            )
            session.add(message)
            await session.commit()

    async def update_step(self, step_dict: StepDict) -> None:
        """
        Update a step (not implemented - messages are immutable in our system).
        """
        pass

    async def delete_step(self, step_id: str) -> None:
        """
        Delete a step (not implemented - messages are immutable in our system).
        """
        pass

    async def get_element(
        self, thread_id: str, element_id: str
    ) -> Optional[Element]:
        """
        Get an element (not implemented - not using file storage yet).
        """
        return None

    async def delete_element(self, element_id: str) -> None:
        """
        Delete an element (not implemented).
        """
        pass

    async def delete_feedback(self, feedback_id: str) -> None:
        """
        Delete feedback (not implemented).
        """
        pass

    async def upsert_feedback(self, feedback_dict: Dict) -> None:
        """
        Upsert feedback (not implemented).
        """
        pass

    async def get_thread_author(self, thread_id: str) -> str:
        """
        Get the author of a thread.
        
        Args:
            thread_id: Thread/conversation ID
            
        Returns:
            User identifier (email)
        """
        async with async_session() as session:
            result = await session.execute(
                select(Conversation).filter(Conversation.id == int(thread_id))
            )
            conversation = result.scalars().first()
            
            if conversation:
                user_result = await session.execute(
                    select(User).filter(User.id == conversation.user_id)
                )
                user = user_result.scalars().first()
                if user:
                    return user.email
            
            return "unknown"

    async def create_element(self, element: Element) -> None:
        """
        Create an element (not implemented - not using file storage yet).
        """
        pass

    async def build_debug_url(self) -> str:
        """
        Build debug URL (not implemented).
        """
        return ""

    async def close(self) -> None:
        """
        Close connections (not needed - using context managers).
        """
        pass
