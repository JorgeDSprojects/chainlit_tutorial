# Phase 6: Threads, History, and User Settings - Implementation Guide

## Overview

This document describes the implementation of Phase 6, which adds thread management, conversation history, dynamic model selection, and persistent user settings to the Chainlit chatbot application.

## Features Implemented

### 6.1 Chainlit Data Layer

**File**: `src/services/chainlit_data_layer.py`

Implements Chainlit's `BaseDataLayer` to persist conversations and messages to our SQLite database.

**Key Methods**:
- `list_threads()` - Lists all conversations for a user with pagination
- `get_thread()` - Retrieves a specific conversation with all messages
- `delete_thread()` - Deletes a conversation and its messages
- `create_step()` - Stores individual messages (user and assistant)
- `update_thread()` - Updates conversation metadata

**How it works**:
- Maps Chainlit's thread concept to our `Conversation` model
- Maps Chainlit's steps to our `Message` model
- Automatically stores messages when users chat
- Enables sidebar history navigation

### 6.2 Conversation Resume

**File**: `src/app.py` - `@cl.on_chat_resume`

Allows users to resume previous conversations from the sidebar.

**Features**:
- Loads conversation history from database
- Restores message history in session
- Displays previous messages in UI
- Maintains conversation context

**How to use**:
1. Start a conversation
2. Send several messages
3. Close the chat or start a new one
4. Click on the old conversation in the sidebar
5. All previous messages will be displayed
6. Continue the conversation seamlessly

### 6.3 Dynamic Ollama Models

**File**: `src/services/llm_service.py` - `get_ollama_models()`

Dynamically fetches available Ollama models from the local Ollama instance.

**Features**:
- Queries `http://localhost:11434/api/tags` for available models
- Automatically populates model selector in UI
- Falls back to "llama2" if API is unavailable
- Temperature slider (0.0 - 1.0) for response creativity

**How to add a new model**:
```bash
# Pull a new model (e.g., phi)
ollama pull phi

# Refresh the chat interface
# The new model will appear in the dropdown
```

**Temperature Settings**:
- 0.0 = Deterministic (same answer every time)
- 0.5 = Balanced
- 1.0 = Creative (varied responses)

### 6.4 Persistent User Settings

**Files**:
- `src/db/models.py` - `UserSettings` model
- `src/services/user_settings_service.py` - Settings management

**Features**:
- Stores user preferences in database
- Persists across sessions and logins
- Settings include:
  - Default Ollama model
  - Preferred temperature
  - Favorite models (for future use)

**Database Schema**:
```sql
CREATE TABLE user_settings (
    id INTEGER PRIMARY KEY,
    user_id INTEGER UNIQUE,
    default_model VARCHAR DEFAULT 'llama2',
    temperature FLOAT DEFAULT 0.7,
    favorite_models JSON,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(id)
);
```

**How it works**:
1. User changes model or temperature in settings
2. Settings are saved to database via `@cl.on_settings_update`
3. On next login, settings are loaded in `@cl.on_chat_start`
4. UI is initialized with user's saved preferences

## Validation Tests

### Test 6.1: Thread Listing
- [x] Login to the application
- [x] Start a new conversation
- [x] Send multiple messages
- [x] Check sidebar shows the conversation
- [x] Conversation title shows message count

### Test 6.2: Conversation Resume
- [x] Have a conversation with 5+ messages
- [x] Close the chat
- [x] Reopen from sidebar history
- [x] Verify all 5 messages are displayed
- [x] Send a new message and verify continuity

### Test 6.3: Dynamic Ollama Models
- [x] Run `ollama pull phi` to add a new model
- [x] Refresh the chat interface
- [x] Verify "phi" appears in model selector
- [x] Select different models and test responses
- [x] Adjust temperature slider and observe changes

### Test 6.4: Persistent Settings
- [x] Change model to "qwen2.5" (or any available model)
- [x] Change temperature to 0.3
- [x] Logout
- [x] Login again
- [x] Verify model is still "qwen2.5"
- [x] Verify temperature is still 0.3

## Database Updates

The `UserSettings` table is automatically created on application startup via SQLAlchemy's `create_all()` method in `main.py`.

No manual migration is required. The table will be created when you first run the application after this update.

## Dependencies Added

- **httpx** - For making HTTP requests to Ollama API

Install with:
```bash
pip install httpx
```

## Configuration

No new configuration variables are required. The system uses existing settings:

- `OLLAMA_BASE_URL` - Already configured in `.env`
- `MAX_CONTEXT_MESSAGES` - Already configured for history limits

## API Endpoints

No new API endpoints were added. All functionality is integrated through Chainlit callbacks.

## Known Limitations

1. **Ollama-only dynamic models**: Currently only Ollama models are dynamically loaded. OpenAI and OpenRouter models remain static.

2. **Basic thread display**: Thread names show as "Nueva Conversación" with message count. Future enhancement could add auto-generated titles based on conversation content.

3. **No thread search**: Users must scroll through sidebar to find old conversations. Search functionality could be added in the future.

4. **Single favorite list**: User settings include a `favorite_models` field that's not yet used in the UI.

## Future Enhancements

1. Auto-generate conversation titles from first message
2. Search and filter threads by date or content
3. Export conversation history
4. Favorite models quick-access in UI
5. Dynamic loading for OpenAI and OpenRouter models
6. Thread tagging and categorization

## Troubleshooting

### Sidebar doesn't show conversations
- Verify database connection is working
- Check that user is authenticated
- Ensure `ChainlitDataLayer` is configured in `app.py`

### Old messages don't load
- Check `create_step()` is being called
- Verify thread_id is set in user session
- Check database for stored messages

### Models list is empty
- Verify Ollama is running on `localhost:11434`
- Check `OLLAMA_BASE_URL` in `.env`
- Ensure at least one model is pulled (`ollama pull llama2`)

### Settings don't persist
- Check `UserSettings` table exists in database
- Verify `@cl.on_settings_update` is saving to DB
- Check user is authenticated when changing settings

## Code Structure

```
src/
├── app.py                          # Main Chainlit callbacks
├── db/
│   └── models.py                   # Database models including UserSettings
└── services/
    ├── chainlit_data_layer.py     # Thread persistence layer
    ├── llm_service.py              # LLM with dynamic models
    └── user_settings_service.py    # User settings management
```

## Conclusion

Phase 6 successfully implements a complete thread management and user settings system, providing users with persistent conversations, dynamic model selection, and personalized preferences that survive across sessions.
