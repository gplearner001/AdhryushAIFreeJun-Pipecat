# Quick Setup: Voyage AI for Embeddings

Your RAG system has been migrated to use **Voyage AI** for embeddings (Anthropic's recommended partner) instead of OpenAI.

## Current Status

The error you're seeing:
```
RAG service not available. Please configure Voyage AI and Supabase.
```

This means you need to add your Voyage API key to the `.env` file.

## Setup Steps

### 1. Get Your Voyage API Key

1. Visit **https://www.voyageai.com/**
2. Sign up for a free account
3. Navigate to the **API Keys** section in your dashboard
4. Create a new API key
5. Copy the key

### 2. Add the Key to Your .env File

Open `/tmp/cc-agent/58029763/project/.env` and replace:

```bash
VOYAGE_API_KEY=your_voyage_api_key_here
```

With your actual key:

```bash
VOYAGE_API_KEY=pa-xxxxxxxxxxxxxxxxxxxxx
```

### 3. Install Python Dependencies

```bash
cd backend
pip install -r requirements.txt
```

This will install the `voyageai` package.

### 4. Restart Your Backend Server

If the backend is running, restart it to load the new environment variable:

```bash
cd backend
python fastapi_app.py
```

Or if using uvicorn:

```bash
cd backend
uvicorn fastapi_app:app --reload --host 0.0.0.0 --port 8000
```

### 5. Verify It's Working

Test the RAG status endpoint:

```bash
curl http://localhost:8000/api/kb/status
```

You should see:

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

## What Changed?

- **Embedding Model**: OpenAI `text-embedding-ada-002` → Voyage AI `voyage-2`
- **API Key**: `OPENAI_API_KEY` → `VOYAGE_API_KEY`
- **Package**: `openai` → `voyageai`
- **Optimizations**: Added support for document vs query embeddings

## Why Voyage AI?

1. **Anthropic Partnership** - Official recommended embedding provider
2. **Claude Optimization** - Embeddings tuned for use with Claude
3. **Better Performance** - Input type specialization (document/query)
4. **Same Pricing** - $0.0001 per 1K tokens (similar to OpenAI)

## Troubleshooting

### "Voyage client not initialized"

- Verify `VOYAGE_API_KEY` is set in `.env`
- Check the key is valid (starts with `pa-`)
- Ensure no extra spaces in the `.env` file

### "Module not found: voyageai"

```bash
cd backend
pip install voyageai
```

### Backend still shows error after adding key

- Restart the backend server
- Check the backend console logs for detailed errors
- Verify the `.env` file is in the correct location

## Need Help?

- Check `EMBEDDING_MIGRATION.md` for detailed migration guide
- Review `RAG_SETUP_GUIDE.md` for full RAG setup
- Visit Voyage AI docs: https://docs.voyageai.com/
