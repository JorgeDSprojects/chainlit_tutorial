# Phase 6 Testing Guide

## Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Setup Environment
```bash
cp .env.example .env
# Edit .env and set CHAINLIT_AUTH_SECRET to a secure value
```

### 3. Start the Application
```bash
python main.py
```
Access at: http://localhost:8000

### 4. Create Test User
Use the API to create a test user:
```bash
curl -X POST http://localhost:8000/api/users \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "testpass123"
  }'
```

## Testing Scenarios

### ✅ Test 6.1: Data Layer and Thread Management

**Goal**: Verify conversation history sidebar appears and works

1. Login with test@example.com / testpass123
2. **Expected**: Sidebar shows on the left with "Threads" section
3. Start a new conversation (should auto-create)
4. Send several messages (at least 3 exchanges)
5. **Expected**: Conversation appears in sidebar with title
6. Refresh page
7. **Expected**: Conversation still visible in sidebar

### ✅ Test 6.2: Resume Conversations

**Goal**: Verify conversations can be resumed and continued

1. Start a conversation with exactly 5 messages:
   - User: "Hello"
   - Bot: (response)
   - User: "What is Python?"
   - Bot: (response)
   - User: "Tell me more"
   - Bot: (response)
2. Note the conversation in the sidebar
3. Start a new conversation (click "New Chat" or similar)
4. **Expected**: New empty conversation starts
5. Click on the previous conversation in the sidebar
6. **Expected**: 
   - All 5 previous messages display in order
   - Message shows: "✅ Conversación cargada con 5 mensajes..."
7. Send a new message: "Continue from where we left off"
8. **Expected**: Bot responds with context from previous messages

### ✅ Test 6.3: Dynamic Ollama Models

**Goal**: Verify model list is dynamically loaded from Ollama

**Prerequisites**: Ollama must be running on localhost:11434

1. Ensure you have at least 2 models:
   ```bash
   ollama list
   # If you only have one model:
   ollama pull phi
   ```

2. Start a new conversation
3. Open Chat Settings (gear icon or settings panel)
4. **Expected**: 
   - "Modelo" dropdown shows all installed Ollama models
   - Temperature slider visible (0.0 - 1.0)
   - Default model is "llama2" (or first in your list)

5. Select a different model (e.g., "phi")
6. Adjust temperature to 0.9
7. Send a message
8. **Expected**: Response uses the selected model and temperature

9. Pull a new model while app is running:
   ```bash
   ollama pull mistral
   ```
10. Reload the page
11. **Expected**: "mistral" appears in the model list

### ✅ Test 6.4: Persistent User Settings

**Goal**: Verify settings persist across sessions

1. Login as test@example.com
2. Open Chat Settings
3. Change settings:
   - Model: "phi" (or any non-default)
   - Temperature: 0.3
4. **Expected**: Message shows "✅ Configuración guardada: phi a temperatura 0.3"
5. Send a message to verify settings work
6. Close browser completely (or logout)
7. Login again as test@example.com
8. **Expected**:
   - Chat Settings automatically shows:
     - Model: "phi"
     - Temperature: 0.3
9. Send a message
10. **Expected**: Uses the saved settings

### ✅ Test 6.5: Multi-User Settings Isolation

**Goal**: Verify each user has independent settings

1. Create second test user:
   ```bash
   curl -X POST http://localhost:8000/api/users \
     -H "Content-Type: application/json" \
     -d '{
       "email": "user2@example.com",
       "password": "password123"
     }'
   ```

2. Login as test@example.com
3. Set Model: "phi", Temperature: 0.2
4. Logout
5. Login as user2@example.com
6. **Expected**: Settings should be default (llama2, 0.7)
7. Set Model: "mistral", Temperature: 0.9
8. Logout
9. Login as test@example.com again
10. **Expected**: Settings still "phi" and 0.2

## Feature Validation Checklist

### Data Layer (6.1)
- [ ] Sidebar appears with "Threads" section
- [ ] New conversations auto-create threads
- [ ] Conversation list shows all user's chats
- [ ] Thread titles display correctly
- [ ] Can delete old conversations

### Resume Conversations (6.2)
- [ ] Previous messages load when clicking thread
- [ ] User and assistant messages display correctly
- [ ] System messages display if present
- [ ] Conversation context preserved
- [ ] Can continue conversation after resume
- [ ] Message count shown correctly

### Dynamic Models (6.3)
- [ ] Model list reflects installed Ollama models
- [ ] New models appear after pull + refresh
- [ ] Temperature slider works (0.0 - 1.0)
- [ ] Selected model affects responses
- [ ] Fallback to default if Ollama unavailable

### Persistent Settings (6.4)
- [ ] Settings load on chat start
- [ ] Settings save when changed
- [ ] Settings persist across logout/login
- [ ] Settings isolated per user
- [ ] Default settings work for new users

## Common Issues

### Issue: Sidebar doesn't show
**Solution**: 
- Check that data layer is registered in app.py
- Verify user is logged in
- Create at least one conversation

### Issue: Models not loading
**Solution**:
- Verify Ollama is running: `curl http://localhost:11434/api/tags`
- Check OLLAMA_BASE_URL in .env
- Look for errors in console logs

### Issue: Settings not persisting
**Solution**:
- Check database has user_settings table
- Verify user_id in session
- Check logs for save_settings errors

### Issue: Can't resume conversation
**Solution**:
- Verify conversation exists in database
- Check conversation_id in thread data
- Ensure get_conversation_history works

## Database Verification

Check data in SQLite:
```bash
sqlite3 chat.db

-- View users
SELECT * FROM users;

-- View conversations
SELECT id, title, user_id, created_at FROM conversations;

-- View messages for conversation
SELECT role, substr(content, 1, 50) as content 
FROM messages 
WHERE conversation_id = 1;

-- View user settings
SELECT * FROM user_settings;
```

## Performance Testing

Test with multiple conversations:
```bash
# Create 10 conversations with multiple messages each
# Verify:
# - Sidebar loads quickly
# - Pagination works if implemented
# - No memory leaks
# - Database queries are efficient
```

## Security Notes

- ✅ CodeQL scan passed with 0 vulnerabilities
- User settings isolated by user_id
- No SQL injection vectors (using SQLAlchemy ORM)
- Authentication required for all features
- Conversation data visible only to owner

## Next Steps After Testing

If all tests pass:
1. Document any edge cases discovered
2. Consider adding automated tests
3. Monitor performance with real usage
4. Gather user feedback
5. Plan future enhancements

## Support

For issues or questions:
- Check `doc/PHASE_6_IMPLEMENTATION.md` for detailed documentation
- Review code comments in implementation files
- Check application logs for error details
