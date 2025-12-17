# Phase 6: Threads, History and Advanced Features - Implementation Guide

## Overview
Phase 6 implements advanced chat features including conversation history, thread management, dynamic model selection, and persistent user settings.

## Features Implemented

### 6.1 Chainlit Data Layer
**File**: `src/services/chainlit_data_layer.py`

Implements Chainlit's `BaseDataLayer` to integrate with the existing database structure:

- **Thread Management**:
  - `list_threads()` - List all conversations for a user with pagination
  - `get_thread()` - Fetch specific conversation with all messages
  - `create_thread()` - Create new conversation
  - `update_thread()` - Update conversation metadata (title)
  - `delete_thread()` - Delete conversation and all messages

- **Step Management** (Messages):
  - `create_step()` - Store messages as "steps" in Chainlit terminology
  - Maps Chainlit step types to database message roles

- **User Management**:
  - `get_user()` - Retrieve user by email
  - `get_thread_author()` - Get conversation owner

### 6.2 Resume Conversations
**File**: `src/app.py` - `@cl.on_chat_resume` callback

When a user clicks on a previous conversation in the sidebar:

1. Loads conversation history from database
2. Populates `cl.user_session["message_history"]` with past messages
3. Displays all previous messages in the chat interface
4. Sets the `conversation_id` to continue in the same thread
5. User can seamlessly continue the conversation

**Validation Steps**:
1. Start a conversation with 5+ messages
2. Close the chat
3. Reopen from history sidebar
4. ✅ All messages should display and you can continue chatting

### 6.3 Dynamic Ollama Models
**Files**: 
- `src/services/llm_service.py` - `get_ollama_models()` function
- `src/app.py` - Dynamic ChatSettings construction

**Features**:
- Fetches available models from Ollama API (`GET /api/tags`)
- Dynamically builds model selector with actual installed models
- Temperature slider (0.0 - 1.0) for response generation control
- Proper URL parsing using `urllib.parse` for robustness

**API Integration**:
```python
# Ollama API endpoint
GET http://localhost:11434/api/tags

# Response format
{
  "models": [
    {"name": "llama2", ...},
    {"name": "phi", ...}
  ]
}
```

**Validation Steps**:
1. Run `ollama pull phi`
2. Refresh chat interface
3. ✅ "phi" should appear in model list

### 6.4 Persistent User Settings
**Files**:
- `src/db/models.py` - `UserSettings` model
- `src/services/user_settings_service.py` - Settings management

**Database Schema**:
```sql
CREATE TABLE user_settings (
    id INTEGER PRIMARY KEY,
    user_id INTEGER UNIQUE,
    default_model VARCHAR,
    temperature FLOAT,
    favorite_models JSON,
    created_at DATETIME,
    updated_at DATETIME,
    FOREIGN KEY(user_id) REFERENCES users (id)
);
```

**Features**:
- Settings automatically loaded on chat start
- Settings persisted when user changes them
- Default values managed through constants:
  - `DEFAULT_MODEL = "llama2"`
  - `DEFAULT_TEMPERATURE = 0.7`

**Service Functions**:
- `get_settings(user_id)` - Retrieve user settings
- `save_settings(user_id, ...)` - Update/create settings
- `get_or_create_settings(user_id)` - Get or initialize defaults

**Validation Steps**:
1. Change model to "qwen2.5" and temperature to 0.7
2. Close session/logout
3. Login again
4. ✅ Settings should persist at "qwen2.5" and 0.7

## Architecture Decisions

### Data Layer Integration
- Chainlit's data layer provides built-in UI for conversation history
- No additional frontend code needed - sidebar automatically appears
- Seamlessly integrates with existing database models

### Message Storage
- Messages stored as Conversation → Message relationships
- Each message has role (user/assistant/system) and content
- Timestamps automatically tracked for ordering

### Settings Management
- One-to-one relationship: User → UserSettings
- Settings table separate from users for flexibility
- JSON field for future extensibility (favorite_models)

### Error Handling
- Graceful fallbacks if Ollama API is unavailable
- Default model list provided when dynamic loading fails
- Settings errors don't break chat functionality

## Configuration

### Environment Variables
No new environment variables required. Uses existing:
- `OLLAMA_BASE_URL` - For fetching available models

### Constants
Defined in `src/services/user_settings_service.py`:
```python
DEFAULT_MODEL = "llama2"
DEFAULT_TEMPERATURE = 0.7
```

## Testing Checklist

### Data Layer
- [ ] Conversation list appears in sidebar
- [ ] Clicking conversation loads history
- [ ] New conversations create new threads
- [ ] Deleting conversation works

### Resume Conversations
- [ ] Previous messages display correctly
- [ ] Can continue conversation after resume
- [ ] Message history preserved in session
- [ ] System messages display if present

### Dynamic Models
- [ ] Model list reflects installed Ollama models
- [ ] Model selection works in chat settings
- [ ] Temperature slider affects response creativity
- [ ] Fallback to default model on API failure

### Persistent Settings
- [ ] Settings load on chat start
- [ ] Settings save when changed
- [ ] Settings persist across sessions
- [ ] Settings per user (not global)

## Dependencies Added
- `aiohttp` - For async HTTP requests to Ollama API

## Code Quality
- ✅ All imports successful
- ✅ No syntax errors
- ✅ Code review feedback addressed
- ✅ Security scan passed (0 vulnerabilities)
- ✅ Proper error handling
- ✅ Constants for maintainability

## Future Enhancements

### Potential Improvements
1. **Favorite Models**: Implement UI for marking models as favorites
2. **Thread Search**: Add search functionality for conversations
3. **Export History**: Allow users to export conversation history
4. **Model Metadata**: Display model size, quantization, etc.
5. **Temperature Presets**: Quick temperature settings (Creative, Balanced, Precise)
6. **Conversation Tags**: Categorize conversations by topic
7. **Sharing**: Share conversations with other users

### Performance Optimizations
1. Cache Ollama model list (refresh periodically)
2. Lazy load conversation history (pagination)
3. Index database for faster queries
4. Compress old conversation data

## Troubleshooting

### Sidebar not showing conversations
- Ensure data layer is registered: `cl.data_layer = ChainlitDataLayer()`
- Check database has conversations for logged-in user
- Verify user authentication is working

### Models not loading
- Check Ollama is running: `curl http://localhost:11434/api/tags`
- Verify `OLLAMA_BASE_URL` in .env
- Check logs for API errors

### Settings not persisting
- Verify `user_settings` table exists in database
- Check user_id is present in session metadata
- Look for errors in `save_settings()` function

## Related Files
- `src/app.py` - Main application with callbacks
- `src/services/chainlit_data_layer.py` - Data layer implementation
- `src/services/llm_service.py` - LLM service with dynamic models
- `src/services/user_settings_service.py` - Settings management
- `src/db/models.py` - Database models including UserSettings
- `requirements.txt` - Dependencies including aiohttp

## References
- [Chainlit Data Layer Documentation](https://docs.chainlit.io/data-persistence/custom)
- [Ollama API Reference](https://github.com/ollama/ollama/blob/main/docs/api.md)
- SQLAlchemy async patterns
