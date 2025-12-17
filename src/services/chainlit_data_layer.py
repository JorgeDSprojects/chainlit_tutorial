"""
Chainlit Data Layer implementation for persistence.
This connects Chainlit's conversation history feature with our existing database.
"""
from typing import Optional, Dict, List
from datetime import datetime
from chainlit.data import BaseDataLayer
from chainlit.types import ThreadDict, Pagination, ThreadFilter, PaginatedResponse
from chainlit.step import StepDict
from sqlalchemy.future import select
from sqlalchemy import desc, func
from src.db.database import async_session
from src.db.models import Conversation, Message, User


class ChainlitDataLayer(BaseDataLayer):
    """
    Custom data layer that integrates Chainlit with our SQLite database.
    Implements conversation history and thread management.
    """
    
    async def get_user(self, identifier: str):
        """Get user by identifier (email)."""
        async with async_session() as session:
            result = await session.execute(
                select(User).filter(User.email == identifier)
            )
            user = result.scalars().first()
            if user:
                return {
                    "id": str(user.id),
                    "identifier": user.email,
                    "metadata": {}
                }
            return None
    
    async def create_user(self, user):
        """Create a new user - not implemented as we handle this via auth."""
        return None
    
    async def get_thread(self, thread_id: str) -> Optional[ThreadDict]:
        """
        Retrieve a specific thread (conversation) with all its messages.
        
        Args:
            thread_id: The Chainlit thread ID (UUID string)
            
        Returns:
            ThreadDict with conversation details and all messages as steps
        """
        async with async_session() as session:
            # Get the conversation by thread_id
            result = await session.execute(
                select(Conversation).filter(Conversation.thread_id == thread_id)
            )
            conversation = result.scalars().first()
            
            if not conversation:
                return None
            
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
                steps.append({
                    "id": str(msg.id),
                    "name": msg.role,
                    "type": step_type,
                    "threadId": thread_id,
                    "parentId": None,
                    "streaming": False,
                    "input": msg.content if msg.role == "user" else "",
                    "output": msg.content if msg.role != "user" else "",
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
                "userIdentifier": None,
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
            
            # Apply pagination
            page = pagination.first or 0
            page_size = 20  # Default page size
            query = query.offset(page).limit(page_size)
            
            # Execute query
            result = await session.execute(query)
            conversations = result.scalars().all()
            
            # Get total count for pagination (efficient count query)
            count_query = select(func.count(Conversation.id))
            if filters.userId:
                count_query = count_query.filter(Conversation.user_id == int(filters.userId))
            count_result = await session.execute(count_query)
            total = count_result.scalar() or 0
            
            # Convert to ThreadDict format (without loading all messages)
            threads = []
            for conv in conversations:
                # Use thread_id if available, otherwise fall back to str(id)
                thread_id = conv.thread_id if conv.thread_id else str(conv.id)
                threads.append({
                    "id": thread_id,
                    "name": conv.title,
                    "createdAt": conv.created_at.isoformat() if conv.created_at else None,
                    "userId": str(conv.user_id),
                    "userIdentifier": None,
                    "steps": [],  # Don't load all steps in list view
                    "metadata": {},
                    "tags": []
                })
            
            return PaginatedResponse(
                data=threads,
                pageInfo={
                    "hasNextPage": page + page_size < total,
                    "startCursor": str(page),
                    "endCursor": str(page + len(threads))
                }
            )
    
    async def delete_thread(self, thread_id: str):
        """
        Delete a thread (conversation) and all its messages.
        
        Args:
            thread_id: The Chainlit thread ID to delete
        """
        async with async_session() as session:
            result = await session.execute(
                select(Conversation).filter(Conversation.thread_id == thread_id)
            )
            conversation = result.scalars().first()
            
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
            
            # Find the conversation by thread_id
            result = await session.execute(
                select(Conversation).filter(Conversation.thread_id == thread_id)
            )
            conversation = result.scalars().first()
            
            if not conversation:
                # Thread doesn't exist yet, skip for now
                # It will be created when the conversation starts
                return
            
            # Determine role from step type
            step_type = step_dict.get("type", "")
            if "user" in step_type:
                role = "user"
                content = step_dict.get("input", "")
            elif "assistant" in step_type:
                role = "assistant"
                content = step_dict.get("output", "")
            else:
                role = "system"
                content = step_dict.get("output", step_dict.get("input", ""))
            
            # Only save if there's content
            if not content:
                return
            
            # Create message
            message = Message(
                conversation_id=conversation.id,
                role=role,
                content=content
            )
            
            session.add(message)
            await session.commit()
    
    async def update_step(self, step_dict: StepDict):
        """Update an existing step - not implemented."""
        pass
    
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
            result = await session.execute(
                select(Conversation).filter(Conversation.thread_id == thread_id)
            )
            conversation = result.scalars().first()
            
            if conversation and name:
                conversation.title = name
                await session.commit()
    
    async def get_thread_author(self, thread_id: str) -> str:
        """Get the author (user identifier) of a thread."""
        async with async_session() as session:
            result = await session.execute(
                select(Conversation).filter(Conversation.thread_id == thread_id)
            )
            conversation = result.scalars().first()
            
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
