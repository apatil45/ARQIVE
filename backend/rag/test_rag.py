"""
Test script for RAG functionality
Run this to verify RAG is working correctly
"""
import asyncio
import sys
import os
# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.vector import VectorDB
from rag.rag_engine import RAGEngine
from config import settings


async def test_rag():
    """Test RAG pipeline"""
    print("🧪 Testing RAG Integration...")
    print(f"Ollama URL: {settings.OLLAMA_BASE_URL}")
    print(f"Ollama Model: {settings.OLLAMA_MODEL}\n")
    
    # Initialize
    vector_db = VectorDB()
    await vector_db.initialize()
    rag_engine = RAGEngine(vector_db)
    
    # Test 1: Check if Ollama is accessible
    print("1️⃣ Testing Ollama connection...")
    try:
        from ollama import Client
        client = Client(host=settings.OLLAMA_BASE_URL)
        models = client.list()
        print(f"   ✅ Ollama is running")
        print(f"   Available models: {[m['name'] for m in models.get('models', [])]}")
        
        if not any(m['name'] == settings.OLLAMA_MODEL for m in models.get('models', [])):
            print(f"   ⚠️  Model '{settings.OLLAMA_MODEL}' not found!")
            print(f"   Run: ollama pull {settings.OLLAMA_MODEL}")
    except Exception as e:
        print(f"   ❌ Cannot connect to Ollama: {e}")
        print(f"   Please start Ollama: ollama serve")
        return
    
    # Test 2: Test embeddings
    print("\n2️⃣ Testing embeddings...")
    try:
        from rag.embeddings import EmbeddingModel
        emb_model = EmbeddingModel()
        test_embedding = await emb_model.embed("test query")
        print(f"   ✅ Embeddings working (dimension: {len(test_embedding)})")
    except Exception as e:
        print(f"   ❌ Embedding error: {e}")
        return
    
    # Test 3: Test query with no documents
    print("\n3️⃣ Testing query with no documents...")
    result = await rag_engine.query("test question", "test_user", 5)
    print(f"   Response: {result['answer'][:100]}...")
    
    # Test 4: Test with sample document (if any exist)
    print("\n4️⃣ Testing with documents (if available)...")
    stats = await vector_db.get_collection_stats()
    print(f"   Documents in database: {stats.get('document_count', 0)}")
    
    if stats.get('document_count', 0) > 0:
        result = await rag_engine.query("What is this document about?", "test_user", 3)
        print(f"   ✅ Query executed")
        print(f"   Answer length: {len(result['answer'])} chars")
        print(f"   Sources: {result['sources']}")
    else:
        print("   ℹ️  No documents in database. Upload a document first to test full RAG.")
    
    print("\n✅ RAG integration test complete!")


if __name__ == "__main__":
    asyncio.run(test_rag())

