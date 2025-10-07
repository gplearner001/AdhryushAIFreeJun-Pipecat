# Quick Fix: RAG Service Not Available

## The Problem

You're seeing this error:
```
503 Service Unavailable - RAG service not available. Please configure Voyage AI and Supabase.
```

## The Solution (3 Steps)

### 1. Get Voyage API Key

Visit: **https://www.voyageai.com/**
- Sign up (free)
- Go to API Keys section
- Create a new key
- Copy it (starts with `pa-`)

### 2. Add to backend/.env

Edit: `/tmp/cc-agent/58029763/project/backend/.env`

Replace this line:
```bash
VOYAGE_API_KEY=your_voyage_api_key_here
```

With your actual key:
```bash
VOYAGE_API_KEY=pa-your-actual-key-here
```

### 3. Restart Backend

Stop the backend (Ctrl+C) and start again:

```bash
cd backend
python fastapi_app.py
```

## Verify It Works

Check the logs when backend starts. You should see:

```
✅ Voyage API Key found: True
✅ RAG Service initialized - Available: True
```

Test the API:
```bash
curl http://localhost:8000/api/kb/status
```

Should return:
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

## Still Not Working?

See `TROUBLESHOOTING.md` for detailed help.

## Why Voyage AI?

Voyage AI is Anthropic's recommended embedding partner, providing embeddings optimized for use with Claude. It replaces OpenAI embeddings in this system.
