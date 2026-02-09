"""
Test script to check if all imports work correctly
Run this before starting the server to catch import errors
"""
import sys

def test_imports():
    """Test all critical imports"""
    errors = []
    
    try:
        from config import settings
        print("✓ Config imported")
    except Exception as e:
        errors.append(f"Config: {e}")
    
    try:
        from auth.users import User, Role
        print("✓ Auth users imported")
    except Exception as e:
        errors.append(f"Auth users: {e}")
    
    try:
        from auth.jwt_handler import create_access_token, verify_token
        print("✓ JWT handler imported")
    except Exception as e:
        errors.append(f"JWT handler: {e}")
    
    try:
        from auth.roles import require_role
        print("✓ Roles imported")
    except Exception as e:
        errors.append(f"Roles: {e}")
    
    try:
        from db.vector import VectorDB
        print("✓ Vector DB imported")
    except Exception as e:
        errors.append(f"Vector DB: {e}")
    
    try:
        from db.sqlite import SQLiteDB
        print("✓ SQLite DB imported")
    except Exception as e:
        errors.append(f"SQLite DB: {e}")
    
    try:
        from documents.ingest import ingest_document
        print("✓ Document ingest imported")
    except Exception as e:
        errors.append(f"Document ingest: {e}")
    
    try:
        from rag.rag_engine import RAGEngine
        print("✓ RAG engine imported")
    except Exception as e:
        errors.append(f"RAG engine: {e}")
    
    try:
        from rag.chunker import Chunker
        print("✓ Chunker imported")
    except Exception as e:
        errors.append(f"Chunker: {e}")
    
    try:
        from rag.embeddings import EmbeddingModel
        print("✓ Embeddings imported")
    except Exception as e:
        errors.append(f"Embeddings: {e}")
    
    if errors:
        print("\n❌ Import errors found:")
        for error in errors:
            print(f"  - {error}")
        return False
    else:
        print("\n✅ All imports successful!")
        return True

if __name__ == "__main__":
    success = test_imports()
    sys.exit(0 if success else 1)


