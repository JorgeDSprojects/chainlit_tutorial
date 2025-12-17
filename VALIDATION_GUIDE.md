# Validation Guide for Chainlit Data Layer

This guide explains how to validate the Chainlit Data Layer implementation.

## Overview

The Chainlit Data Layer integrates our SQLite database with Chainlit's conversation history feature. This allows users to:
- See their conversation history in the sidebar
- Click on old conversations to resume them
- Have messages automatically persisted to the database

## Prerequisites

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure Environment**:
   ```bash
   cp .env.example .env
   # Edit .env and set CHAINLIT_AUTH_SECRET to a secure value
   ```

3. **Initialize Database**:
   ```bash
   python3 init_db.py
   ```

4. **Create Test User** (for testing):
   ```bash
   python3 create_test_user.py
   ```
   This creates a user with:
   - Email: `test@example.com`
   - Password: `test123`

## Validation Steps

### Step 1: Start the Application

```bash
python3 main.py
```

The application should start on `http://localhost:8000`

### Step 2: Login

1. Open your browser to `http://localhost:8000`
2. Log in with the test credentials:
   - Email: `test@example.com`
   - Password: `test123`

**Expected Result**: ✅ You should see a welcome message and the chat interface.

### Step 3: Start a New Conversation

1. Type a message in the chat (e.g., "Hello, this is my first message")
2. Wait for the AI response

**Expected Result**: 
- ✅ The message is sent
- ✅ You receive a response from the AI
- ✅ The conversation is automatically saved to the database

### Step 4: Send Multiple Messages

1. Continue the conversation with 2-3 more messages
2. Each message should be responded to by the AI

**Expected Result**:
- ✅ All messages are displayed in the chat
- ✅ Messages are automatically persisted to the database

### Step 5: Check Sidebar for Conversation History

1. Look for the sidebar (usually on the left side)
2. You should see a list of your conversations

**Expected Result**:
- ✅ The sidebar shows your conversation history
- ✅ Each conversation is listed with its title (default: "Nueva Conversación")
- ✅ Conversations are ordered by most recent first

### Step 6: Start Another Conversation

1. Click the "New Chat" button (if available) or refresh the page
2. Start a new conversation with different messages

**Expected Result**:
- ✅ A new conversation is created
- ✅ The sidebar now shows 2 conversations

### Step 7: Resume an Old Conversation

1. Click on the first conversation in the sidebar
2. The conversation should load with all previous messages

**Expected Result**:
- ✅ The old conversation loads
- ✅ All previous messages are displayed in order
- ✅ You can continue the conversation from where you left off
- ✅ New messages are added to the existing conversation

### Step 8: Verify Database Persistence

You can manually check the database to verify messages are saved:

```bash
sqlite3 chat.db "SELECT * FROM conversations;"
sqlite3 chat.db "SELECT role, content FROM messages LIMIT 5;"
```

**Expected Result**:
- ✅ Conversations table has entries with thread_id values
- ✅ Messages table has all your messages with correct roles (user/assistant)

## Troubleshooting

### Issue: Sidebar doesn't show conversations

**Possible Causes**:
- Data layer not registered correctly
- Database not initialized
- User not logged in

**Solutions**:
1. Check that `cl.data_layer = ChainlitDataLayer()` is in `src/app.py`
2. Verify database tables exist: `sqlite3 chat.db ".tables"`
3. Ensure you're logged in

### Issue: Conversations don't load when clicked

**Possible Causes**:
- thread_id not properly stored
- get_thread() method has issues

**Solutions**:
1. Check the thread_id in the database: `sqlite3 chat.db "SELECT id, thread_id FROM conversations;"`
2. Check server logs for errors

### Issue: Messages not saved

**Possible Causes**:
- create_step() not being called
- Database write error

**Solutions**:
1. Check server logs for database errors
2. Verify the conversation exists before sending messages

## Architecture Notes

### How It Works

1. **When a user starts a new chat**:
   - Chainlit generates a UUID thread_id
   - We create a Conversation record with that thread_id
   - The thread_id links Chainlit's session to our database

2. **When a message is sent**:
   - Chainlit automatically calls `create_step()` on our data layer
   - We save the message to the database linked to the conversation

3. **When listing conversations**:
   - Chainlit calls `list_threads()` with the user's ID
   - We query our database and return conversations as ThreadDict objects

4. **When resuming a conversation**:
   - User clicks on a conversation in the sidebar
   - Chainlit calls `get_thread()` with the thread_id
   - We load all messages from the database and return them as steps
   - Chainlit displays the conversation history

### Key Files

- `src/services/chainlit_data_layer.py` - Main data layer implementation
- `src/db/models.py` - Database models (added thread_id to Conversation)
- `src/app.py` - Chainlit app (registers the data layer)
- `src/services/conversation_service.py` - Conversation management utilities

## Success Criteria

The implementation is successful if:

✅ Users can log in  
✅ New conversations are created automatically  
✅ Messages are sent and received  
✅ Messages are automatically saved to the database  
✅ The sidebar shows conversation history  
✅ Clicking on old conversations loads them correctly  
✅ Resumed conversations show all previous messages  
✅ New messages can be added to resumed conversations  

## Next Steps

After validation, you can:
1. Customize conversation titles (currently defaults to "Nueva Conversación")
2. Add conversation metadata (tags, custom properties)
3. Implement conversation search/filtering
4. Add conversation deletion from the UI
5. Export conversations to different formats
