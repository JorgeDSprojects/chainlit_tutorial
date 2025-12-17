"""
User Settings Service
Manages persistent user preferences for models, temperature, and favorites.
"""
from typing import Optional, Dict, List
from sqlalchemy.future import select
from src.db.database import async_session
from src.db.models import UserSettings, User


async def get_settings(user_id: int) -> Optional[Dict]:
    """
    Get user settings from database.
    
    Args:
        user_id: User ID
        
    Returns:
        Dict with settings or None if not found
    """
    async with async_session() as session:
        result = await session.execute(
            select(UserSettings).filter(UserSettings.user_id == user_id)
        )
        settings = result.scalars().first()
        
        if settings:
            return {
                "default_model": settings.default_model,
                "temperature": settings.temperature,
                "favorite_models": settings.favorite_models or []
            }
        return None


async def save_settings(
    user_id: int,
    default_model: Optional[str] = None,
    temperature: Optional[float] = None,
    favorite_models: Optional[List[str]] = None
) -> Dict:
    """
    Save or update user settings.
    
    Args:
        user_id: User ID
        default_model: Default model name
        temperature: Temperature setting
        favorite_models: List of favorite model names
        
    Returns:
        Updated settings dict
    """
    async with async_session() as session:
        # Check if settings exist
        result = await session.execute(
            select(UserSettings).filter(UserSettings.user_id == user_id)
        )
        settings = result.scalars().first()
        
        if settings:
            # Update existing settings
            if default_model is not None:
                settings.default_model = default_model
            if temperature is not None:
                settings.temperature = temperature
            if favorite_models is not None:
                settings.favorite_models = favorite_models
        else:
            # Create new settings
            settings = UserSettings(
                user_id=user_id,
                default_model=default_model or "llama2",
                temperature=temperature if temperature is not None else 0.7,
                favorite_models=favorite_models or []
            )
            session.add(settings)
        
        await session.commit()
        await session.refresh(settings)
        
        return {
            "default_model": settings.default_model,
            "temperature": settings.temperature,
            "favorite_models": settings.favorite_models or []
        }


async def get_or_create_settings(user_id: int) -> Dict:
    """
    Get user settings or create default ones if they don't exist.
    
    Args:
        user_id: User ID
        
    Returns:
        Settings dict
    """
    settings = await get_settings(user_id)
    
    if settings is None:
        # Create default settings
        settings = await save_settings(
            user_id=user_id,
            default_model="llama2",
            temperature=0.7,
            favorite_models=[]
        )
    
    return settings
