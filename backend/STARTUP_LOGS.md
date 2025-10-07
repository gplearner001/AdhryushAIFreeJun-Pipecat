# Expected Backend Startup Logs

## When RAG Service is Properly Configured

When you start the backend server with `python fastapi_app.py`, you should see logs in this order:

### 1. RAG Service Initialization (from rag_service.py)

These logs appear when `rag_service.py` is imported:

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

### 2. FastAPI App Startup (from fastapi_app.py)

Then the main application logs:

```
INFO:__main__:Starting Teler FastAPI Service on port 8000
INFO:__main__:Teler library available: False
INFO:__main__:Environment variables loaded:
INFO:__main__:  - ANTHROPIC_API_KEY: NOT_SET (or ***xxxx if configured)
INFO:__main__:  - SARVAM_API_KEY: NOT_SET (or ***xxxx if configured)
INFO:__main__:  - VOYAGE_API_KEY: ***here (last 4 chars of your key)
INFO:__main__:Claude AI available: True/False
INFO:__main__:Sarvam AI available: True/False
INFO:__main__:RAG Service available: True
INFO:__main__:WebRTC VAD available: True/False
INFO:     Started server process [12345]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

## When RAG Service is NOT Configured

If the Voyage API key is missing or invalid:

```
INFO:rag_service:Voyage API Key found: False
WARNING:rag_service:VOYAGE_API_KEY environment variable not set!
INFO:rag_service:Supabase URL found: True
INFO:rag_service:Supabase Key found: True
INFO:rag_service:Voyage library available: True
INFO:rag_service:Supabase library available: True
INFO:rag_service:RAG Service initialized - Available: False
INFO:rag_service:  - Voyage Client: False
INFO:rag_service:  - Supabase Client: True
```

Then in fastapi_app.py:

```
INFO:__main__:  - VOYAGE_API_KEY: ***here
INFO:__main__:RAG Service available: False
```

## Troubleshooting Based on Logs

### If you see: `Voyage API Key found: False`

**Problem:** The `VOYAGE_API_KEY` environment variable is not loaded

**Fix:**
1. Check that `backend/.env` exists
2. Verify the file contains: `VOYAGE_API_KEY=your_actual_key`
3. Make sure there are no quotes around the value
4. Restart the backend server

### If you see: `Voyage library available: False`

**Problem:** The `voyageai` package is not installed

**Fix:**
```bash
cd backend
pip install voyageai
```

### If you see: `Supabase client initialization failed`

**Problem:** Supabase connection failed

**Fix:**
1. Verify `VITE_SUPABASE_URL` in `backend/.env`
2. Verify `VITE_SUPABASE_ANON_KEY` in `backend/.env`
3. Check Supabase project is active

### If you see: `RAG Service available: False`

**Problem:** Either Voyage or Supabase (or both) not configured

**Fix:**
- Check the specific logs above it
- Both `Voyage Client: True` AND `Supabase Client: True` are required
- Fix whichever is showing `False`

## How to View Logs

### During Startup

The logs appear in your terminal when you run:

```bash
cd backend
python fastapi_app.py
```

### While Running

You can also check the status via API:

```bash
curl http://localhost:8000/api/kb/status
```

Response when working:
```json
{
  "success": true,
  "data": {
    "available": true,
    "voyage_configured": true,
    "supabase_configured": true,
    "supported_file_types": ["pdf", "doc", "docx", "txt", "xls", "xlsx"]
  }
}
```

Response when NOT working:
```json
{
  "success": true,
  "data": {
    "available": false,
    "voyage_configured": false,
    "supabase_configured": true,
    "supported_file_types": ["pdf", "doc", "docx", "txt", "xls", "xlsx"]
  }
}
```

## Key Points

1. **Logs appear on import** - The RAG service logs appear as soon as `rag_service.py` is imported, before the FastAPI app fully starts

2. **Both required** - You need BOTH Voyage AI AND Supabase for `available: true`

3. **Environment matters** - The `.env` file must be in the `backend/` directory

4. **Restart required** - You MUST restart the backend server after changing `.env`

5. **Check both places** - Look for logs in terminal AND test the `/api/kb/status` endpoint

## Complete Example

Here's what a successful startup looks like:

```bash
$ cd backend
$ python fastapi_app.py

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
INFO:__main__:Starting Teler FastAPI Service on port 8000
INFO:__main__:Teler library available: False
INFO:__main__:Environment variables loaded:
INFO:__main__:  - ANTHROPIC_API_KEY: NOT_SET
INFO:__main__:  - SARVAM_API_KEY: NOT_SET
INFO:__main__:  - VOYAGE_API_KEY: ***xxxx
INFO:__main__:Claude AI available: False
INFO:__main__:Sarvam AI available: False
INFO:__main__:RAG Service available: True  ✅
INFO:__main__:WebRTC VAD available: True
INFO:     Started server process [12345]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

The key indicator is: **`RAG Service available: True`** ✅
