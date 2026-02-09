"""
Diagnostic script to check why queries return no results
"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.vector import VectorDB
from db.sqlite import SQLiteDB
from rag.rag_engine import RAGEngine
from rag.embeddings import EmbeddingModel
import chromadb

async def diagnose():
    print("=" * 60)
    print("ARQIVE Query Issue Diagnostic")
    print("=" * 60)
    print()
    
    # 1. Check ChromaDB
    print("1. Checking ChromaDB Vector Database...")
    vector_db = VectorDB()
    await vector_db.initialize()
    
    try:
        stats = await vector_db.get_collection_stats()
        chunk_count = stats.get("document_count", 0)
        print(f"   [OK] Total chunks in vector DB: {chunk_count}")
        
        if chunk_count == 0:
            print("   [WARNING] Vector DB is EMPTY! This is the problem.")
            print("   -> Documents need to be re-uploaded/re-ingested")
    except Exception as e:
        print(f"   [ERROR] Error checking vector DB: {e}")
    
    print()
    
    # 2. Check SQLite documents
    print("2. Checking SQLite Document Metadata...")
    sqlite_db = SQLiteDB()
    await sqlite_db.initialize()
    
    try:
        # Check for admin user documents
        admin_docs = await sqlite_db.get_user_documents("admin", 0, 100)
        print(f"   [OK] Documents in SQLite for 'admin': {len(admin_docs)}")
        
        if len(admin_docs) > 0:
            print(f"   Sample documents:")
            for doc in admin_docs[:3]:
                print(f"     - {doc.get('filename', 'unknown')} (ID: {doc.get('id', 'unknown')[:8]}...)")
        else:
            print("   [WARNING] No documents found for admin user")
    except Exception as e:
        print(f"   [ERROR] Error checking SQLite: {e}")
    
    print()
    
    # 3. Check if embeddings match metadata
    print("3. Checking Vector DB Metadata...")
    try:
        client = chromadb.PersistentClient(path="data/chroma_db")
        collection = client.get_collection("documents")
        
        # Get a sample of documents
        sample = collection.get(limit=5)
        if sample and len(sample.get("ids", [])) > 0:
            print(f"   [OK] Found {len(sample['ids'])} sample chunks")
            if len(sample.get("metadatas", [])) > 0:
                sample_metadata = sample["metadatas"][0]
                print(f"   Sample metadata keys: {list(sample_metadata.keys())}")
                print(f"   Sample uploaded_by: {sample_metadata.get('uploaded_by', 'NOT SET')}")
                print(f"   Sample document_id: {sample_metadata.get('document_id', 'NOT SET')}")
            else:
                print("   [WARNING] No metadata found in chunks")
        else:
            print("   [WARNING] No chunks found in vector DB")
    except Exception as e:
        print(f"   [ERROR] Error checking vector DB metadata: {e}")
    
    print()
    
    # 4. Test a query
    print("4. Testing Query Flow...")
    try:
        rag_engine = RAGEngine(vector_db, sqlite_db)
        
        # Test embedding generation
        emb_model = EmbeddingModel()
        test_embedding = await emb_model.embed("test query")
        print(f"   [OK] Query embedding generated (dim: {len(test_embedding)})")
        
        # Test vector search
        filter_dict = {"uploaded_by": "admin"}
        results = await vector_db.query(
            query_embedding=test_embedding,
            n_results=5,
            filter_dict=filter_dict
        )
        
        doc_count = len(results.get("documents", []))
        print(f"   [OK] Vector search returned {doc_count} chunks")
        
        if doc_count == 0:
            print("   [WARNING] Vector search returned NO results with filter")
            print("   -> This could mean:")
            print("     1. No chunks have 'uploaded_by': 'admin' in metadata")
            print("     2. All chunks were lost when ChromaDB was recreated")
            print("     3. Documents need to be re-ingested")
        else:
            print(f"   [OK] Found {doc_count} chunks - query should work!")
            # Check metadata
            metadatas = results.get("metadatas", [])
            if metadatas:
                print(f"   Sample metadata: uploaded_by={metadatas[0].get('uploaded_by')}")
    except Exception as e:
        print(f"   [ERROR] Error testing query: {e}")
        import traceback
        traceback.print_exc()
    
    print()
    print("=" * 60)
    print("Diagnosis Complete")
    print("=" * 60)
    print()
    print("RECOMMENDATIONS:")
    print()
    
    # Provide recommendations
    try:
        if chunk_count == 0:
            print("[CRITICAL] ISSUE: Vector DB is empty")
            print("   SOLUTION: Re-upload or re-ingest your documents")
            print("   -> Use the upload page in the frontend")
            print("   -> Or run: python scripts/reingest_documents.py")
        elif len(admin_docs) > 0 and chunk_count == 0:
            print("[CRITICAL] ISSUE: Documents exist in SQLite but not in Vector DB")
            print("   SOLUTION: Re-ingest documents to regenerate embeddings")
            print("   -> Run: python scripts/reingest_documents.py")
        else:
            print("[OK] Vector DB has data - check metadata matching above")
    except:
        pass

if __name__ == "__main__":
    asyncio.run(diagnose())

