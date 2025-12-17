"""
User Settings Service for managing user preferences
"""
from typing import Optional, Dict, Any, List
from sqlalchemy.future import select
from src.db.database import async_session
from src.db.models import User, UserSettings


class UserSettingsService:
    """Service for managing user settings"""
    
    async def get_settings(self, user_email: str) -> Optional[Dict[str, Any]]:
        """
        Get user settings by email.
        Returns default settings if none exist.
        """
        async with async_session() as session:
            # Get user
            result = await session.execute(
                select(User).filter(User.email == user_email)
            )
            user = result.scalars().first()
            
            if not user:
                return None
            
            # Get or create settings
            settings_result = await session.execute(
                select(UserSettings).filter(UserSettings.user_id == user.id)
            )
            settings = settings_result.scalars().first()
            
            if settings:
                return {
                    "default_model": settings.default_model,
                    "temperature": settings.temperature,
                    "favorite_models": settings.favorite_models or []
                }
            else:
                # Return defaults
                return {
                    "default_model": "llama2",
                    "temperature": 0.7,
                    "favorite_models": []
                }
    
    async def save_settings(
        self, 
        user_email: str,
        default_model: Optional[str] = None,
        temperature: Optional[float] = None,
        favorite_models: Optional[List[str]] = None
    ) -> bool:
        """
        Save or update user settings.
        Returns True if successful, False otherwise.
        """
        async with async_session() as session:
            # Get user
            result = await session.execute(
                select(User).filter(User.email == user_email)
            )
            user = result.scalars().first()
            
            if not user:
                return False
            
            # Get or create settings
            settings_result = await session.execute(
                select(UserSettings).filter(UserSettings.user_id == user.id)
            )
            settings = settings_result.scalars().first()
            
            if not settings:
                # Create new settings
                settings = UserSettings(user_id=user.id)
                session.add(settings)
                await session.flush()  # Ensure the object is persisted before updating
            
            # Update settings
            if default_model is not None:
                settings.default_model = default_model
            
            if temperature is not None:
                settings.temperature = temperature
            
            if favorite_models is not None:
                settings.favorite_models = favorite_models
            
            await session.commit()
            return True
    
    async def add_favorite_model(self, user_email: str, model_name: str) -> bool:
        """
        Add a model to user's favorites.
        """
        async with async_session() as session:
            # Get user
            result = await session.execute(
                select(User).filter(User.email == user_email)
            )
            user = result.scalars().first()
            
            if not user:
                return False
            
            # Get or create settings
            settings_result = await session.execute(
                select(UserSettings).filter(UserSettings.user_id == user.id)
            )
            settings = settings_result.scalars().first()
            
            if not settings:
                settings = UserSettings(user_id=user.id, favorite_models=[model_name])
                session.add(settings)
                await session.flush()
            else:
                favorites = settings.favorite_models or []
                if model_name not in favorites:
                    favorites.append(model_name)
                    settings.favorite_models = favorites
            
            await session.commit()
            return True
    
    async def remove_favorite_model(self, user_email: str, model_name: str) -> bool:
        """
        Remove a model from user's favorites.
        """
        async with async_session() as session:
            # Get user
            result = await session.execute(
                select(User).filter(User.email == user_email)
            )
            user = result.scalars().first()
            
            if not user:
                return False
            
            # Get settings
            settings_result = await session.execute(
                select(UserSettings).filter(UserSettings.user_id == user.id)
            )
            settings = settings_result.scalars().first()
            
            if settings and settings.favorite_models:
                favorites = settings.favorite_models
                if model_name in favorites:
                    favorites.remove(model_name)
                    settings.favorite_models = favorites
                    await session.commit()
            
            return True


# Singleton instance
user_settings_service = UserSettingsService()
