#!/usr/bin/env python3
"""
Knowledge Base API Routes
Handles CRUD operations for knowledge bases, documents, and RAG queries.
Uses PostgreSQL with pgvector for vector database.
"""

import os
import logging
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, status
from pydantic import BaseModel
from psycopg2.extras import RealDictCursor
import io

from rag_service import rag_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/kb", tags=["knowledge_base"])

class KnowledgeBaseCreate(BaseModel):
    name: str
    description: Optional[str] = None
    user_id: str

class KnowledgeBaseUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None

class KnowledgeBaseResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    user_id: str
    is_active: bool
    created_at: str
    updated_at: str
    document_count: Optional[int] = 0

class DocumentResponse(BaseModel):
    id: str
    knowledge_base_id: str
    filename: str
    file_type: str
    file_size: Optional[int]
    processing_status: str
    error_message: Optional[str]
    created_at: str
    processed_at: Optional[str]

class SearchRequest(BaseModel):
    query: str
    knowledge_base_id: str
    limit: Optional[int] = 5
    threshold: Optional[float] = 0.5

@router.post("/knowledge-bases", status_code=status.HTTP_201_CREATED)
async def create_knowledge_base(kb: KnowledgeBaseCreate):
    """Create a new knowledge base."""
    if not rag_service.is_available():
        raise HTTPException(
            status_code=503,
            detail="RAG service not available. Please configure Voyage AI and PostgreSQL."
        )

    conn = None
    try:
        conn = rag_service.get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute("""
            INSERT INTO knowledge_bases (name, description, user_id, is_active)
            VALUES (%s, %s, %s, %s)
            RETURNING *
        """, (kb.name, kb.description, kb.user_id, True))

        created_kb = cur.fetchone()
        conn.commit()

        if not created_kb:
            raise HTTPException(status_code=500, detail="Failed to create knowledge base")

        return {
            'success': True,
            'data': dict(created_kb),
            'message': 'Knowledge base created successfully'
        }

    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Error creating knowledge base: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create knowledge base: {str(e)}")
    finally:
        if conn:
            rag_service.return_connection(conn)

@router.get("/knowledge-bases")
async def list_knowledge_bases(user_id: str):
    """List all knowledge bases for a user."""
    if not rag_service.is_available():
        raise HTTPException(
            status_code=503,
            detail="RAG service not available"
        )

    conn = None
    try:
        conn = rag_service.get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute("""
            SELECT
                kb.*,
                COUNT(d.id) as document_count
            FROM knowledge_bases kb
            LEFT JOIN documents d ON kb.id = d.knowledge_base_id
            WHERE kb.user_id = %s
            GROUP BY kb.id
            ORDER BY kb.created_at DESC
        """, (user_id,))

        knowledge_bases = [dict(row) for row in cur.fetchall()]

        return {
            'success': True,
            'data': knowledge_bases,
            'count': len(knowledge_bases)
        }

    except Exception as e:
        logger.error(f"Error listing knowledge bases: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to list knowledge bases: {str(e)}")
    finally:
        if conn:
            rag_service.return_connection(conn)

@router.get("/knowledge-bases/{kb_id}")
async def get_knowledge_base(kb_id: str):
    """Get details of a specific knowledge base."""
    if not rag_service.is_available():
        raise HTTPException(status_code=503, detail="RAG service not available")

    conn = None
    try:
        conn = rag_service.get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute("""
            SELECT * FROM knowledge_bases WHERE id = %s
        """, (kb_id,))

        kb_data = cur.fetchone()

        if not kb_data:
            raise HTTPException(status_code=404, detail="Knowledge base not found")

        cur.execute("""
            SELECT COUNT(*) as count FROM documents WHERE knowledge_base_id = %s
        """, (kb_id,))

        doc_count = cur.fetchone()['count']

        kb_dict = dict(kb_data)
        kb_dict['document_count'] = doc_count

        return {
            'success': True,
            'data': kb_dict
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting knowledge base: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get knowledge base: {str(e)}")
    finally:
        if conn:
            rag_service.return_connection(conn)

@router.put("/knowledge-bases/{kb_id}")
async def update_knowledge_base(kb_id: str, kb_update: KnowledgeBaseUpdate):
    """Update a knowledge base."""
    if not rag_service.is_available():
        raise HTTPException(status_code=503, detail="RAG service not available")

    conn = None
    try:
        update_data = kb_update.dict(exclude_unset=True)

        if not update_data:
            raise HTTPException(status_code=400, detail="No update data provided")

        conn = rag_service.get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        set_clause = ", ".join([f"{key} = %s" for key in update_data.keys()])
        values = list(update_data.values()) + [kb_id]

        cur.execute(f"""
            UPDATE knowledge_bases
            SET {set_clause}, updated_at = NOW()
            WHERE id = %s
            RETURNING *
        """, values)

        updated_kb = cur.fetchone()
        conn.commit()

        if not updated_kb:
            raise HTTPException(status_code=404, detail="Knowledge base not found")

        return {
            'success': True,
            'data': dict(updated_kb),
            'message': 'Knowledge base updated successfully'
        }

    except HTTPException:
        raise
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Error updating knowledge base: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update knowledge base: {str(e)}")
    finally:
        if conn:
            rag_service.return_connection(conn)

@router.delete("/knowledge-bases/{kb_id}")
async def delete_knowledge_base(kb_id: str):
    """Delete a knowledge base and all its documents."""
    if not rag_service.is_available():
        raise HTTPException(status_code=503, detail="RAG service not available")

    conn = None
    try:
        conn = rag_service.get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute("""
            DELETE FROM knowledge_bases WHERE id = %s RETURNING *
        """, (kb_id,))

        deleted_kb = cur.fetchone()
        conn.commit()

        if not deleted_kb:
            raise HTTPException(status_code=404, detail="Knowledge base not found")

        return {
            'success': True,
            'message': 'Knowledge base deleted successfully'
        }

    except HTTPException:
        raise
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Error deleting knowledge base: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete knowledge base: {str(e)}")
    finally:
        if conn:
            rag_service.return_connection(conn)

@router.post("/documents/upload")
async def upload_document(
    knowledge_base_id: str = Form(...),
    file: UploadFile = File(...)
):
    """Upload and process a document."""
    if not rag_service.is_available():
        raise HTTPException(
            status_code=503,
            detail="RAG service not available"
        )

    conn = None
    try:
        file_extension = file.filename.split('.')[-1].lower()

        supported_types = ['pdf', 'doc', 'docx', 'txt', 'xls', 'xlsx']
        if file_extension not in supported_types:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type. Supported types: {', '.join(supported_types)}"
            )

        file_content = await file.read()
        file_size = len(file_content)

        conn = rag_service.get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute("""
            INSERT INTO documents (knowledge_base_id, filename, file_type, file_size, processing_status)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING *
        """, (knowledge_base_id, file.filename, file_extension, file_size, 'pending'))

        document = cur.fetchone()
        conn.commit()

        if not document:
            raise HTTPException(status_code=500, detail="Failed to create document record")

        document_id = document['id']

        cur.execute("""
            UPDATE documents SET processing_status = 'processing' WHERE id = %s
        """, (document_id,))
        conn.commit()

        file_stream = io.BytesIO(file_content)

        process_result = await rag_service.process_document(
            document_id=str(document_id),
            file_content=file_stream,
            file_type=file_extension,
            knowledge_base_id=knowledge_base_id
        )

        if process_result['success']:
            return {
                'success': True,
                'data': {
                    'document_id': str(document_id),
                    'filename': file.filename,
                    'chunks_created': process_result['chunks_created'],
                    'total_chunks': process_result['total_chunks']
                },
                'message': 'Document uploaded and processed successfully'
            }
        else:
            return {
                'success': False,
                'data': {
                    'document_id': str(document_id),
                    'filename': file.filename
                },
                'error': process_result.get('error', 'Processing failed'),
                'message': 'Document uploaded but processing failed'
            }

    except HTTPException:
        raise
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Error uploading document: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to upload document: {str(e)}")
    finally:
        if conn:
            rag_service.return_connection(conn)

@router.get("/documents")
async def list_documents(knowledge_base_id: str):
    """List all documents in a knowledge base."""
    if not rag_service.is_available():
        raise HTTPException(status_code=503, detail="RAG service not available")

    conn = None
    try:
        conn = rag_service.get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute("""
            SELECT * FROM documents
            WHERE knowledge_base_id = %s
            ORDER BY created_at DESC
        """, (knowledge_base_id,))

        documents = [dict(row) for row in cur.fetchall()]

        return {
            'success': True,
            'data': documents,
            'count': len(documents)
        }

    except Exception as e:
        logger.error(f"Error listing documents: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to list documents: {str(e)}")
    finally:
        if conn:
            rag_service.return_connection(conn)

@router.delete("/documents/{document_id}")
async def delete_document(document_id: str):
    """Delete a document and its chunks."""
    if not rag_service.is_available():
        raise HTTPException(status_code=503, detail="RAG service not available")

    conn = None
    try:
        conn = rag_service.get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute("""
            DELETE FROM documents WHERE id = %s RETURNING *
        """, (document_id,))

        deleted_doc = cur.fetchone()
        conn.commit()

        if not deleted_doc:
            raise HTTPException(status_code=404, detail="Document not found")

        return {
            'success': True,
            'message': 'Document deleted successfully'
        }

    except HTTPException:
        raise
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Error deleting document: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete document: {str(e)}")
    finally:
        if conn:
            rag_service.return_connection(conn)

@router.post("/search")
async def search_knowledge_base(search_req: SearchRequest):
    """Search knowledge base using semantic similarity."""
    if not rag_service.is_available():
        raise HTTPException(status_code=503, detail="RAG service not available")

    try:
        results = await rag_service.search_knowledge_base(
            query=search_req.query,
            knowledge_base_id=search_req.knowledge_base_id,
            limit=search_req.limit,
            threshold=search_req.threshold
        )

        return {
            'success': True,
            'data': results,
            'count': len(results)
        }

    except Exception as e:
        logger.error(f"Error searching knowledge base: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to search knowledge base: {str(e)}")

@router.get("/status")
async def rag_status():
    """Check RAG service status."""
    return {
        'success': True,
        'data': {
            'available': rag_service.is_available(),
            'voyage_configured': rag_service.voyage_client is not None,
            'database_configured': rag_service.db_pool is not None,
            'supported_file_types': ['pdf', 'doc', 'docx', 'txt', 'xls', 'xlsx']
        }
    }
