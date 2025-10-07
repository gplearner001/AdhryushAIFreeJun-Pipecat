# RAG Knowledge Base System - Setup Guide

## Overview

This system enables users to create knowledge bases, upload documents, and have the AI (Claude) answer questions based on those documents using RAG (Retrieval-Augmented Generation).

## Architecture

### Backend Components

1. **rag_service.py** - Core RAG functionality
   - Document text extraction (PDF, DOCX, TXT, XLS, XLSX)
   - Text chunking with token-based splitting
   - Embedding generation using Voyage AI (Anthropic's recommended partner)
   - Semantic search using pgvector
   - Context retrieval for Claude

2. **knowledge_base_routes.py** - API endpoints
   - Knowledge base CRUD operations
   - Document upload and processing
   - Semantic search
   - Status checks

3. **claude_service.py** - Updated to support RAG
   - Queries knowledge base for relevant context
   - Includes context in Claude prompts
   - Only answers from knowledge base when KB is selected

### Frontend Components

1. **KnowledgeBaseManager.tsx**
   - Create/delete knowledge bases
   - Upload multiple documents at once
   - View document processing status
   - Manage documents

2. **AIConversationPanel.tsx** - Updated
   - Knowledge base selector dropdown
   - Shows which KB is active
   - Sends KB ID with queries

### Database Schema

Tables:
- `knowledge_bases` - Stores KB metadata
- `documents` - Tracks uploaded documents
- `document_chunks` - Stores text chunks with embeddings

## Required Environment Variables

Add to backend `.env`:

```bash
VOYAGE_API_KEY=your_voyage_api_key_here
VITE_SUPABASE_URL=your_supabase_url
VITE_SUPABASE_ANON_KEY=your_supabase_anon_key
ANTHROPIC_API_KEY=your_anthropic_api_key
```

**Note:** Get your Voyage API key from https://www.voyageai.com/ (Anthropic's recommended embedding partner)

## Setup Steps

### 1. Install Python Dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 2. Setup Database

The database migration is ready to be applied. When Supabase is available, run:

```sql
-- The migration file create_knowledge_base_tables.sql contains:
-- - pgvector extension
-- - knowledge_bases, documents, document_chunks tables
-- - RLS policies
-- - Semantic search function
```

### 3. Start Backend Server

```bash
cd backend
python fastapi_app.py
```

The server will start on http://localhost:8000

### 4. Start Frontend

```bash
npm run dev
```

## Usage Flow

### Creating a Knowledge Base

1. Open the application
2. Click "New Knowledge Base" button
3. Enter name and description
4. Click "Create"

### Uploading Documents

1. Select a knowledge base from the list
2. Click "Upload" button
3. Select one or multiple files
4. Wait for processing to complete
5. Documents will show status: pending → processing → completed/failed

### Supported File Types

- PDF (.pdf)
- Word documents (.doc, .docx)
- Text files (.txt)
- Excel spreadsheets (.xls, .xlsx)

### Asking Questions

1. In the AI Conversation panel, select a knowledge base from dropdown
2. Type your question
3. Claude will answer based ONLY on the knowledge base documents
4. If no KB is selected, Claude answers normally without restrictions

## How RAG Works

1. **Document Upload**
   - Text is extracted from the file
   - Text is split into chunks (1000 tokens with 200 overlap)
   - Each chunk gets an embedding vector
   - Chunks stored in database with embeddings

2. **Query Processing**
   - User question gets converted to embedding
   - Semantic search finds most relevant chunks
   - Top 5 most similar chunks retrieved
   - Chunks combined into context (max 2000 tokens)

3. **Response Generation**
   - Context + question sent to Claude
   - Claude generates answer based only on context
   - If info not in context, Claude says so

## API Endpoints

### Knowledge Base Management

- `POST /api/kb/knowledge-bases` - Create KB
- `GET /api/kb/knowledge-bases?user_id={id}` - List KBs
- `GET /api/kb/knowledge-bases/{kb_id}` - Get KB details
- `PUT /api/kb/knowledge-bases/{kb_id}` - Update KB
- `DELETE /api/kb/knowledge-bases/{kb_id}` - Delete KB

### Document Management

- `POST /api/kb/documents/upload` - Upload document
- `GET /api/kb/documents?knowledge_base_id={id}` - List documents
- `DELETE /api/kb/documents/{doc_id}` - Delete document

### Search

- `POST /api/kb/search` - Semantic search
  ```json
  {
    "query": "your question",
    "knowledge_base_id": "kb-id",
    "limit": 5,
    "threshold": 0.5
  }
  ```

### Status

- `GET /api/kb/status` - Check RAG service availability

## Key Features

1. **Multiple Knowledge Bases** - Users can create and manage multiple KBs
2. **Multi-file Upload** - Upload multiple documents at once
3. **Real-time Processing** - See processing status in real-time
4. **Semantic Search** - Uses vector similarity for accurate retrieval
5. **Context-aware Responses** - Claude only answers from KB when selected
6. **File Type Support** - Handles common document formats
7. **User Isolation** - RLS ensures users only see their own data

## Security

- Row Level Security (RLS) enabled on all tables
- Users can only access their own knowledge bases
- JWT-based authentication through Supabase
- No direct database access from frontend

## Performance Considerations

- HNSW index for fast vector search
- Token-based chunking for optimal context
- Async processing for document uploads
- Efficient context retrieval (max 2000 tokens)

## Troubleshooting

### Documents stuck in "processing"

Check backend logs for errors. Common issues:
- Missing Voyage API key
- Invalid file format
- File too large or corrupted

### No results from search

- Ensure embeddings were generated
- Lower the similarity threshold
- Check if documents were processed successfully

### Database errors

- Verify Supabase connection
- Check if pgvector extension is enabled
- Ensure RLS policies are set correctly

## Future Enhancements

Potential improvements:
- Batch document processing
- Custom chunk sizes
- Multiple embedding models
- Citation tracking
- Advanced search filters
- Document preview
- Usage analytics
