"""
Chainlit Data Layer Implementation for Thread and Message Persistence
"""
from typing import Optional, Dict, List
from datetime import datetime, timezone
from chainlit.data import BaseDataLayer, queue_until_user_message
from chainlit.types import (
    ThreadDict, 
    Pagination, 
    ThreadFilter, 
    PaginatedResponse,
    Feedback,
    PageInfo
)
from chainlit.step import StepDict
from chainlit.element import ElementDict
from chainlit import User
from sqlalchemy.future import select
from sqlalchemy import desc, func
from src.db.database import async_session
from src.db.models import User as DBUser, Conversation, Message


class ChainlitDataLayer(BaseDataLayer):
    """Custom data layer to persist threads and messages in our database"""
    
    async def get_user(self, identifier: str) -> Optional[Dict]:
        """Get user by identifier (email)"""
        async with async_session() as session:
            result = await session.execute(
                select(DBUser).filter(DBUser.email == identifier)
            )
            user = result.scalars().first()
            if user:
                return {
                    "id": str(user.id),
                    "identifier": user.email,
                    "metadata": {"created_at": user.created_at.isoformat()}
                }
        return None
    
    async def create_user(self, user: User) -> Optional[Dict]:
        """Create a new user - not needed as we handle this in auth"""
        return await self.get_user(user.identifier)
    
    async def delete_feedback(self, feedback_id: str) -> bool:
        """Delete feedback - not implemented yet"""
        return True
    
    async def upsert_feedback(self, feedback: Feedback) -> str:
        """Upsert feedback - not implemented yet"""
        return feedback.id or "feedback_id"
    
    @queue_until_user_message()
    async def create_element(self, element: "ElementDict"):
        """Create an element (file, image, etc) - not implemented yet"""
        pass
    
    async def get_element(
        self, thread_id: str, element_id: str
    ) -> Optional[ElementDict]:
        """Get an element by ID - not implemented yet"""
        return None
    
    @queue_until_user_message()
    async def delete_element(self, element_id: str, thread_id: Optional[str] = None):
        """Delete an element - not implemented yet"""
        pass
    
    @queue_until_user_message()
    async def create_step(self, step_dict: StepDict):
        """Create a step (message) in the database"""
        async with async_session() as session:
            # Extract thread_id and determine conversation
            thread_id = step_dict.get("threadId")
            if not thread_id:
                return
            
            try:
                conversation_id = int(thread_id)
            except (ValueError, TypeError):
                return
            
            # Only store user and assistant messages
            step_type = step_dict.get("type", "")
            if step_type not in ["user_message", "assistant_message"]:
                return
            
            # Map step type to role
            role = "user" if step_type == "user_message" else "assistant"
            
            # Get content from output or input
            content = step_dict.get("output", "") or step_dict.get("input", "")
            
            if not content:
                return
            
            # Create message
            message = Message(
                conversation_id=conversation_id,
                role=role,
                content=content
            )
            session.add(message)
            await session.commit()
    
    @queue_until_user_message()
    async def update_step(self, step_dict: StepDict):
        """Update a step - we append-only in our implementation"""
        pass
    
    @queue_until_user_message()
    async def delete_step(self, step_id: str):
        """Delete a step - not implemented"""
        pass
    
    async def get_thread_author(self, thread_id: str) -> str:
        """Get the author (user email) of a thread"""
        async with async_session() as session:
            try:
                conversation_id = int(thread_id)
                result = await session.execute(
                    select(Conversation).filter(Conversation.id == conversation_id)
                )
                conversation = result.scalars().first()
                if conversation:
                    user_result = await session.execute(
                        select(DBUser).filter(DBUser.id == conversation.user_id)
                    )
                    user = user_result.scalars().first()
                    return user.email if user else ""
            except (ValueError, TypeError):
                pass
        return ""
    
    async def delete_thread(self, thread_id: str):
        """Delete a thread (conversation) and all its messages"""
        async with async_session() as session:
            try:
                conversation_id = int(thread_id)
                result = await session.execute(
                    select(Conversation).filter(Conversation.id == conversation_id)
                )
                conversation = result.scalars().first()
                if conversation:
                    await session.delete(conversation)
                    await session.commit()
            except (ValueError, TypeError):
                pass
    
    async def list_threads(
        self, pagination: Pagination, filters: ThreadFilter
    ) -> PaginatedResponse[ThreadDict]:
        """List threads (conversations) for a user with pagination"""
        async with async_session() as session:
            # Get user_id from filter
            user_identifier = filters.userId if filters else None
            
            if not user_identifier:
                return PaginatedResponse(
                    data=[],
                    pageInfo=PageInfo(hasNextPage=False, endCursor=None)
                )
            
            # Get user
            user_result = await session.execute(
                select(DBUser).filter(DBUser.email == user_identifier)
            )
            user = user_result.scalars().first()
            if not user:
                return PaginatedResponse(
                    data=[],
                    pageInfo=PageInfo(hasNextPage=False, endCursor=None)
                )
            
            # Build query for conversations
            query = (
                select(Conversation)
                .filter(Conversation.user_id == user.id)
                .order_by(desc(Conversation.created_at))
            )
            
            # Apply pagination
            first = pagination.first if pagination else 20
            cursor = pagination.cursor if pagination else None
            
            if cursor:
                try:
                    # Cursor is the conversation ID
                    cursor_id = int(cursor)
                    query = query.filter(Conversation.id < cursor_id)
                except (ValueError, TypeError):
                    pass
            
            query = query.limit(first + 1)  # Fetch one extra to check if there's more
            
            result = await session.execute(query)
            conversations = result.scalars().all()
            
            # Check if there are more results
            has_next_page = len(conversations) > first
            if has_next_page:
                conversations = conversations[:first]
            
            # Convert to ThreadDict
            threads = []
            for conv in conversations:
                # Get message count for this conversation
                count_result = await session.execute(
                    select(func.count(Message.id)).filter(
                        Message.conversation_id == conv.id
                    )
                )
                message_count = count_result.scalar() or 0
                
                thread_dict: ThreadDict = {
                    "id": str(conv.id),
                    "createdAt": conv.created_at.isoformat(),
                    "name": f"{conv.title} ({message_count} mensajes)" if message_count > 0 else conv.title,
                    "userId": str(user.id),
                    "userIdentifier": user.email,
                    "tags": None,
                    "metadata": {"message_count": message_count},
                    "steps": [],
                    "elements": None
                }
                threads.append(thread_dict)
            
            # Determine end cursor
            end_cursor = str(conversations[-1].id) if conversations else None
            
            return PaginatedResponse(
                data=threads,
                pageInfo=PageInfo(
                    hasNextPage=has_next_page,
                    endCursor=end_cursor
                )
            )
    
    async def get_thread(self, thread_id: str) -> Optional[ThreadDict]:
        """Get a specific thread with all its messages"""
        async with async_session() as session:
            try:
                conversation_id = int(thread_id)
                
                # Get conversation
                result = await session.execute(
                    select(Conversation).filter(Conversation.id == conversation_id)
                )
                conversation = result.scalars().first()
                
                if not conversation:
                    return None
                
                # Get user
                user_result = await session.execute(
                    select(DBUser).filter(DBUser.id == conversation.user_id)
                )
                user = user_result.scalars().first()
                
                if not user:
                    return None
                
                # Get messages
                messages_result = await session.execute(
                    select(Message)
                    .filter(Message.conversation_id == conversation_id)
                    .order_by(Message.created_at)
                )
                messages = messages_result.scalars().all()
                
                # Convert messages to StepDict format
                steps = []
                for msg in messages:
                    step_type = "user_message" if msg.role == "user" else "assistant_message"
                    step: StepDict = {
                        "name": msg.role,
                        "type": step_type,
                        "id": f"step_{msg.id}",
                        "threadId": thread_id,
                        "parentId": None,
                        "command": None,
                        "streaming": False,
                        "waitForAnswer": None,
                        "isError": False,
                        "metadata": {},
                        "tags": None,
                        "input": msg.content if msg.role == "user" else "",
                        "output": msg.content if msg.role == "assistant" else "",
                        "createdAt": msg.created_at.isoformat(),
                        "start": None,
                        "end": None,
                        "generation": None,
                        "showInput": False,
                        "defaultOpen": False,
                        "language": None,
                        "feedback": None
                    }
                    steps.append(step)
                
                thread_dict: ThreadDict = {
                    "id": thread_id,
                    "createdAt": conversation.created_at.isoformat(),
                    "name": conversation.title,
                    "userId": str(user.id),
                    "userIdentifier": user.email,
                    "tags": None,
                    "metadata": {},
                    "steps": steps,
                    "elements": None
                }
                
                return thread_dict
                
            except (ValueError, TypeError):
                return None
    
    async def update_thread(
        self,
        thread_id: str,
        name: Optional[str] = None,
        user_id: Optional[str] = None,
        metadata: Optional[Dict] = None,
        tags: Optional[List[str]] = None,
    ):
        """Update thread metadata"""
        async with async_session() as session:
            try:
                conversation_id = int(thread_id)
                result = await session.execute(
                    select(Conversation).filter(Conversation.id == conversation_id)
                )
                conversation = result.scalars().first()
                
                if conversation:
                    if name:
                        conversation.title = name
                    await session.commit()
                    
            except (ValueError, TypeError):
                pass
    
    async def build_debug_url(self) -> str:
        """Build debug URL - not needed for local development"""
        return ""
    
    async def close(self) -> None:
        """Close any resources - not needed"""
        pass
