# RAG Service Setup - Complete Guide

## Current Issue

You're seeing:
```
503 Service Unavailable
{"detail":"RAG service not available. Please configure Voyage AI and Supabase."}
```

And after running `python fastapi_app.py`, you're **NOT seeing** these logs:
```
Voyage API Key found: True
RAG Service initialized - Available: True
```

## Why You Don't See the Logs

The logs you're looking for come from the `rag_service.py` file when it initializes. These logs will appear in the terminal when you run the backend server **IF**:

1. ✅ The `backend/.env` file exists with proper values
2. ✅ The Python dependencies are installed (`voyageai`, `supabase`, `tiktoken`)
3. ✅ The backend server is started fresh (not reloaded)

## Step-by-Step Fix

### Step 1: Verify backend/.env File Exists

```bash
cat /tmp/cc-agent/58029763/project/backend/.env
```

You should see:
```bash
VOYAGE_API_KEY=your_voyage_api_key_here
VITE_SUPABASE_URL=https://cxfryeeoxpcktpuhfnje.supabase.co
VITE_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

If the file doesn't exist or is empty, create it with the above content.

### Step 2: Get Voyage API Key

1. Visit: **https://www.voyageai.com/**
2. Sign up (free account)
3. Create API key
4. Copy the key (starts with `pa-`)

### Step 3: Update backend/.env

Edit `/tmp/cc-agent/58029763/project/backend/.env` and replace:

```bash
VOYAGE_API_KEY=your_voyage_api_key_here
```

With your actual key:

```bash
VOYAGE_API_KEY=pa-xxxxxxxxxxxxxxxxxxxxxxxxxx
```

### Step 4: Install Python Dependencies

**CRITICAL:** You must install the required packages:

```bash
cd /tmp/cc-agent/58029763/project/backend
pip install -r requirements.txt
```

This installs:
- `voyageai` - For embeddings
- `supabase` - For database
- `tiktoken` - For tokenization
- Other dependencies

If `pip` is not available, try:
```bash
python3 -m pip install -r requirements.txt
```

Or:
```bash
pip3 install -r requirements.txt
```

### Step 5: Start Backend Server

**Important:** You must start from the `backend/` directory OR ensure the `.env` file is loaded:

```bash
cd /tmp/cc-agent/58029763/project/backend
python fastapi_app.py
```

Or:
```bash
cd /tmp/cc-agent/58029763/project/backend
python3 fastapi_app.py
```

### Step 6: Check the Logs

When the server starts, you should see these logs **in order**:

#### First - RAG Service Initialization:
```
INFO:rag_service:Voyage API Key found: True
INFO:rag_service:Supabase URL found: True
INFO:rag_service:Supabase Key found: True
INFO:rag_service:Voyage library available: True
INFO:rag_service:Supabase library available: True
INFO:rag_service:Voyage AI client initialized successfully
INFO:rag_service:Supabase client initialized successfully
INFO:rag_service:RAG Service initialized - Available: True
INFO:rag_service:  - Voyage Client: True
INFO:rag_service:  - Supabase Client: True
```

#### Then - FastAPI Startup:
```
INFO:__main__:Starting Teler FastAPI Service on port 8000
INFO:__main__:  - VOYAGE_API_KEY: ***xxxx
INFO:__main__:RAG Service available: True
INFO:     Uvicorn running on http://0.0.0.0:8000
```

## Verification

### Test 1: Check Logs

Look for this specific line in the startup logs:
```
INFO:__main__:RAG Service available: True
```

### Test 2: Test the API

```bash
curl http://localhost:8000/api/kb/status
```

Expected response:
```json
{
  "success": true,
  "data": {
    "available": true,
    "voyage_configured": true,
    "supabase_configured": true
  }
}
```

### Test 3: Try Creating a Knowledge Base

From the frontend, try to create a knowledge base. If it works, the service is running correctly.

## Common Problems

### Problem 1: "ModuleNotFoundError: No module named 'voyageai'"

**Solution:** Install dependencies:
```bash
cd backend
pip install voyageai supabase tiktoken
```

### Problem 2: Still seeing "Available: False" after adding key

**Checklist:**
- [ ] Is the key in `backend/.env` (not just project root `.env`)?
- [ ] Did you remove quotes around the key value?
- [ ] Did you restart the backend server completely?
- [ ] Is the key valid (starts with `pa-`)?

### Problem 3: Not seeing RAG service logs at all

**Possible causes:**
- The `rag_service.py` module failed to import (check for errors)
- Dependencies not installed
- Python environment issue

**Solution:** Run this test:
```bash
cd backend
python3 -c "from rag_service import rag_service; print('Available:', rag_service.is_available())"
```

If this fails, you'll see the exact error.

### Problem 4: Logs show "Voyage library available: False"

**Solution:** Install the voyageai package:
```bash
pip install voyageai
```

## Important Notes

1. **Two .env files:** The project root `.env` is for frontend. The `backend/.env` is for backend. You need BOTH.

2. **Must restart:** Changing `.env` requires a full backend restart (stop with Ctrl+C, then start again).

3. **Dependencies required:** The Python packages MUST be installed. The server won't work without them.

4. **Real API key needed:** You cannot use `your_voyage_api_key_here` - you need a real key from Voyage AI.

5. **Free tier available:** Voyage AI offers a free tier for development/testing.

## File Structure

```
project/
├── .env                          # Frontend env (Supabase config)
└── backend/
    ├── .env                      # Backend env (CRITICAL - must have Voyage key!)
    ├── .env.example              # Template
    ├── requirements.txt          # Python dependencies
    ├── rag_service.py            # RAG service (logs appear from here)
    └── fastapi_app.py            # Main server (checks rag_service)
```

## Summary

The 503 error occurs because:
1. The Voyage API key is not set to a real value
2. The `rag_service.is_available()` returns `False`
3. The knowledge base routes reject requests

To fix:
1. Get a real Voyage API key from voyageai.com
2. Add it to `backend/.env`
3. Install dependencies with `pip install -r requirements.txt`
4. Restart the backend server
5. Verify logs show "RAG Service available: True"

## Need Help?

- See `QUICK_FIX.md` for a 3-step quick fix
- See `TROUBLESHOOTING.md` for detailed troubleshooting
- See `STARTUP_LOGS.md` to understand what logs to expect
- See `VOYAGE_SETUP.md` for Voyage AI setup details
