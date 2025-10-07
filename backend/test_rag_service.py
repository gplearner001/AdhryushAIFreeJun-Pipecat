#!/usr/bin/env python3
"""
Test script to diagnose RAG service initialization
Run this to see detailed debugging information
"""

import os
import logging
from dotenv import load_dotenv

logging.basicConfig(
    level=logging.DEBUG,
    format='%(levelname)s:%(name)s:%(message)s'
)

logger = logging.getLogger(__name__)

print("=" * 60)
print("RAG Service Diagnostic Test")
print("=" * 60)

load_dotenv()

print("\n1. Environment Variables:")
print(f"   VOYAGE_API_KEY: {'***' + os.getenv('VOYAGE_API_KEY', 'NOT_SET')[-4:] if os.getenv('VOYAGE_API_KEY') else 'NOT_SET'}")
print(f"   DATABASE_URL: {os.getenv('DATABASE_URL', 'NOT_SET')[:30]}...")

print("\n2. Testing Package Imports:")

try:
    import voyageai
    print("   ✓ voyageai imported successfully")
    VOYAGE_AVAILABLE = True
except ImportError as e:
    print(f"   ✗ voyageai import failed: {e}")
    VOYAGE_AVAILABLE = False

try:
    import psycopg2
    print("   ✓ psycopg2 imported successfully")
    PSYCOPG2_AVAILABLE = True
except ImportError as e:
    print(f"   ✗ psycopg2 import failed: {e}")
    PSYCOPG2_AVAILABLE = False

try:
    import tiktoken
    print("   ✓ tiktoken imported successfully")
except ImportError as e:
    print(f"   ✗ tiktoken import failed: {e}")

print("\n3. Testing Client Initialization:")

if VOYAGE_AVAILABLE and os.getenv('VOYAGE_API_KEY'):
    try:
        voyage_client = voyageai.Client(api_key=os.getenv('VOYAGE_API_KEY'))
        print("   ✓ Voyage AI client initialized successfully")
    except Exception as e:
        print(f"   ✗ Voyage AI client initialization failed: {e}")
else:
    print(f"   ✗ Cannot initialize Voyage client - Available: {VOYAGE_AVAILABLE}, Key present: {bool(os.getenv('VOYAGE_API_KEY'))}")

if PSYCOPG2_AVAILABLE and os.getenv('DATABASE_URL'):
    try:
        conn = psycopg2.connect(os.getenv('DATABASE_URL'))
        print("   ✓ PostgreSQL connection successful")
        conn.close()
    except Exception as e:
        print(f"   ✗ PostgreSQL connection failed: {e}")
else:
    print(f"   ✗ Cannot test PostgreSQL - Available: {PSYCOPG2_AVAILABLE}, URL present: {bool(os.getenv('DATABASE_URL'))}")

print("\n4. Importing RAG Service:")
try:
    from rag_service import rag_service
    print("   ✓ rag_service imported successfully")
    print(f"\n5. RAG Service Status:")
    print(f"   Available: {rag_service.is_available()}")
    print(f"   Voyage Client: {rag_service.voyage_client is not None}")
    print(f"   DB Pool: {rag_service.db_pool is not None}")
except Exception as e:
    print(f"   ✗ Failed to import rag_service: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("Diagnostic Complete")
print("=" * 60)
