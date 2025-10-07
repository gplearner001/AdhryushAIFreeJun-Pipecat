# Embedding Migration: OpenAI to Voyage AI

## Overview

The RAG service has been migrated from OpenAI's `text-embedding-ada-002` to **Voyage AI's `voyage-2` model**. Voyage AI is Anthropic's recommended embedding partner and provides embeddings optimized for use with Claude.

## Why Voyage AI?

1. **Anthropic's Recommendation** - Official partner for embeddings
2. **Claude Optimization** - Embeddings specifically tuned for Claude models
3. **High Quality** - State-of-the-art retrieval performance
4. **Specialized Models** - Input type differentiation (document vs query)

## Key Changes

### 1. API Client

**Before (OpenAI):**
```python
from openai import OpenAI
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
```

**After (Voyage AI):**
```python
import voyageai
client = voyageai.Client(api_key=os.getenv('VOYAGE_API_KEY'))
```

### 2. Embedding Generation

**Before (OpenAI):**
```python
response = client.embeddings.create(
    input=text,
    model="text-embedding-ada-002"
)
embedding = response.data[0].embedding
```

**After (Voyage AI):**
```python
result = client.embed(
    texts=[text],
    model="voyage-2",
    input_type="document"  # or "query" for search queries
)
embedding = result.embeddings[0]
```

### 3. Input Type Differentiation

Voyage AI supports optimizing embeddings based on usage:

- **`input_type="document"`** - For indexing documents
- **`input_type="query"`** - For search queries

This improves retrieval accuracy by optimizing embeddings for their specific use case.

## Setup Instructions

### 1. Get Voyage API Key

1. Visit https://www.voyageai.com/
2. Sign up for an account
3. Navigate to API Keys section
4. Generate a new API key

### 2. Update Environment Variables

Update your backend `.env` file:

```bash
# Remove or comment out
# OPENAI_API_KEY=your_openai_key

# Add Voyage AI key
VOYAGE_API_KEY=your_voyage_api_key_here
```

### 3. Install Dependencies

```bash
cd backend
pip install -r requirements.txt
```

The `voyageai` package will be installed automatically.

### 4. Restart Backend Server

```bash
cd backend
python fastapi_app.py
```

## Migration Notes

### For Existing Data

If you have existing embeddings generated with OpenAI's ada-002:

**Option 1: Keep existing embeddings** (recommended if working well)
- Old embeddings will continue to work
- New documents will use Voyage AI embeddings
- Slight inconsistency in embedding space but generally acceptable

**Option 2: Regenerate all embeddings** (for optimal performance)
- Delete all document chunks from database
- Re-upload all documents
- All embeddings will be in same space

```sql
-- Clear all chunks (optional, only if regenerating)
DELETE FROM document_chunks;

-- Reset document processing status
UPDATE documents SET processing_status = 'pending', processed_at = NULL;
```

### Embedding Dimensions

- **OpenAI ada-002**: 1536 dimensions
- **Voyage AI voyage-2**: 1024 dimensions

If using Option 2 (regenerating), you may want to update your vector column if it's dimensionally constrained.

## Model Comparison

| Feature | OpenAI ada-002 | Voyage AI voyage-2 |
|---------|---------------|-------------------|
| Dimensions | 1536 | 1024 |
| Input Type Support | No | Yes |
| Claude Integration | General | Optimized |
| Pricing | $0.0001/1K tokens | $0.0001/1K tokens |
| Performance | Excellent | Excellent (better for Claude) |

## Troubleshooting

### "Voyage client not initialized"

- Check that `VOYAGE_API_KEY` is set in `.env`
- Verify the key is valid
- Ensure `voyageai` package is installed

### "Failed to generate embedding"

- Check API key permissions
- Verify network connectivity
- Check Voyage AI status page
- Review backend logs for detailed error

### Reduced search quality

If you notice degraded search quality:
1. Consider regenerating all embeddings (Option 2)
2. Adjust similarity threshold in search
3. Ensure input_type is correct ("document" vs "query")

## Benefits of This Change

1. **Better Integration** - Embeddings optimized for Claude
2. **Input Specialization** - Different embeddings for docs vs queries
3. **Future-Proof** - Aligned with Anthropic's ecosystem
4. **Performance** - Smaller dimension count (1024 vs 1536) = faster search
5. **Consistency** - Single vendor for LLM + embeddings

## Resources

- [Voyage AI Documentation](https://docs.voyageai.com/)
- [Voyage AI Pricing](https://www.voyageai.com/pricing)
- [Anthropic + Voyage Partnership](https://www.anthropic.com/news/voyage-embeddings)
- [voyage-2 Model Card](https://docs.voyageai.com/docs/embeddings)

## Support

For issues or questions:
- Voyage AI: support@voyageai.com
- Check backend logs: `backend/logs/` or console output
- Review RAG_SETUP_GUIDE.md for general setup
