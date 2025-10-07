# Troubleshooting: RAG Service Not Available

## The Error

```
503 Service Unavailable
{"detail":"RAG service not available. Please configure Voyage AI and Supabase."}
```

## Root Causes

This error occurs when the RAG service cannot initialize properly. There are two main requirements:

1. **Voyage AI API Key** - For generating embeddings
2. **Supabase Connection** - For storing and querying data

Both must be properly configured for the service to be available.

## Solution Steps

### Step 1: Check Environment Variables

The backend needs a `.env` file in the `backend/` directory with these variables:

```bash
# backend/.env
VOYAGE_API_KEY=your_voyage_api_key_here
VITE_SUPABASE_URL=https://cxfryeeoxpcktpuhfnje.supabase.co
VITE_SUPABASE_ANON_KEY=your_supabase_anon_key
```

**Important:** Make sure the `.env` file is in the `backend/` directory, not just the project root.

### Step 2: Get Voyage API Key

If you haven't already:

1. Go to **https://www.voyageai.com/**
2. Sign up for an account (free tier available)
3. Navigate to **API Keys** in your dashboard
4. Create a new API key
5. Copy the key (starts with `pa-`)

### Step 3: Update backend/.env

Open `/tmp/cc-agent/58029763/project/backend/.env` and add your Voyage API key:

```bash
VOYAGE_API_KEY=pa-your-actual-key-here
```

### Step 4: Install Python Dependencies

Make sure all required packages are installed:

```bash
cd backend
pip install -r requirements.txt
```

This will install:
- `voyageai` - For embeddings
- `supabase` - For database
- Other dependencies

### Step 5: Restart Backend Server

**IMPORTANT:** You must restart the backend server for environment variables to be loaded.

```bash
# Stop the current backend server (Ctrl+C)

# Then start it again
cd backend
python fastapi_app.py
```

### Step 6: Verify Service Status

Check the backend logs when it starts. You should see:

```
INFO:     Voyage API Key found: True
INFO:     Supabase URL found: True
INFO:     Supabase Key found: True
INFO:     Voyage library available: True
INFO:     Supabase library available: True
INFO:     Voyage AI client initialized successfully
INFO:     Supabase client initialized successfully
INFO:     RAG Service initialized - Available: True
INFO:       - Voyage Client: True
INFO:       - Supabase Client: True
```

You can also test via API:

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
    "supabase_configured": true,
    "supported_file_types": ["pdf", "doc", "docx", "txt", "xls", "xlsx"]
  }
}
```

## Common Issues

### Issue 1: "Voyage API Key found: False"

**Problem:** Environment variable not loaded

**Solutions:**
- Check that `backend/.env` file exists
- Verify the file has `VOYAGE_API_KEY=your_key_here` (no quotes, no spaces)
- Restart the backend server
- Make sure you're running the server from the backend directory OR the project root

### Issue 2: "Module not found: voyageai"

**Problem:** Package not installed

**Solution:**
```bash
cd backend
pip install voyageai
```

### Issue 3: "Supabase client initialization failed"

**Problem:** Invalid Supabase credentials

**Solutions:**
- Verify `VITE_SUPABASE_URL` is correct
- Verify `VITE_SUPABASE_ANON_KEY` is correct
- Check if Supabase project is active
- Ensure no extra spaces in the `.env` file

### Issue 4: Still shows error after adding key

**Problem:** Backend server not restarted

**Solution:**
- Stop the backend server completely (Ctrl+C)
- Wait 2-3 seconds
- Start it again: `python fastapi_app.py`
- Environment variables are only loaded at startup

### Issue 5: "Invalid API key" from Voyage

**Problem:** Wrong or expired API key

**Solutions:**
- Verify you copied the full key from Voyage dashboard
- Check the key hasn't expired
- Try generating a new key
- Make sure there are no spaces or quotes around the key

## Debug Mode

To see detailed logging, you can add to your `.env`:

```bash
LOG_LEVEL=DEBUG
```

Then check backend console output for detailed error messages.

## File Locations

Make sure files are in the correct locations:

```
project/
├── .env                    # Frontend environment variables
└── backend/
    ├── .env                # Backend environment variables (REQUIRED!)
    ├── .env.example        # Example template
    ├── rag_service.py      # RAG service code
    ├── requirements.txt    # Python dependencies
    └── fastapi_app.py      # Backend server
```

## Testing the Fix

After following all steps:

1. **Restart backend server**
2. **Check backend console logs** - Look for "RAG Service initialized - Available: True"
3. **Test the status endpoint**: `curl http://localhost:8000/api/kb/status`
4. **Try creating a knowledge base** from the frontend

## Still Having Issues?

If you've followed all steps and still see the error:

1. **Check backend console output** for specific error messages
2. **Verify all three requirements:**
   - ✅ Voyage API key is valid
   - ✅ Supabase connection is working
   - ✅ Backend server was restarted

3. **Check the specific error in logs:**
   - "Failed to initialize Voyage AI client" - Issue with API key
   - "Failed to initialize Supabase client" - Issue with database connection
   - Both initialized but still not available - Check `is_available()` logic

## Quick Checklist

- [ ] Created `backend/.env` file
- [ ] Added `VOYAGE_API_KEY` with actual key (from voyageai.com)
- [ ] Added `VITE_SUPABASE_URL`
- [ ] Added `VITE_SUPABASE_ANON_KEY`
- [ ] Ran `pip install -r requirements.txt`
- [ ] Restarted backend server
- [ ] Checked backend logs show "Available: True"
- [ ] Tested `/api/kb/status` endpoint

## Need More Help?

- Review `VOYAGE_SETUP.md` for Voyage AI setup details
- Review `EMBEDDING_MIGRATION.md` for migration details
- Review `RAG_SETUP_GUIDE.md` for full RAG setup
- Check Voyage AI docs: https://docs.voyageai.com/
