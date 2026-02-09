"""
Script to re-ingest documents from SQLite into vector database
Use this if vector DB was cleared (e.g., after restart with in-memory DB)
"""
import asyncio
import os
import sys
import aiosqlite

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.vector import VectorDB
from db.sqlite import SQLiteDB
from rag.chunker import Chunker
from rag.embeddings import EmbeddingModel
from config import settings


async def reingest_documents():
    """Re-ingest all documents from SQLite into vector DB"""
    print("Re-ingesting documents into vector database...")
    
    # Initialize databases
    vector_db = VectorDB()
    sqlite_db = SQLiteDB()
    
    await vector_db.initialize()
    await sqlite_db.initialize()
    
    # Get all documents from SQLite
    documents = await get_all_documents_from_sqlite(sqlite_db.db_path)
    
    if not documents:
        print("[ERROR] No documents found in SQLite database")
        return
    
    print(f"Found {len(documents)} documents to re-ingest")
    
    chunker = Chunker()
    embedding_model = EmbeddingModel()
    
    total_chunks = 0
    
    for doc in documents:
        file_path = doc['file_path']
        document_id = doc['id']
        filename = doc['filename']
        uploaded_by = doc['uploaded_by']
        file_type = doc['file_type']
        
        print(f"\nProcessing: {filename}")
        
        if not os.path.exists(file_path):
            print(f"   [WARNING] File not found: {file_path}")
            continue
        
        try:
            # Extract text
            from documents.ingest import extract_text
            text = await extract_text(file_path, file_type)
            
            if not text or len(text.strip()) == 0:
                print(f"   [WARNING] Could not extract text")
                continue
            
            # Chunk
            chunks = chunker.chunk_text(text)
            print(f"   Created {len(chunks)} chunks")
            
            # Generate embeddings
            embeddings = await embedding_model.embed_batch([chunk["text"] for chunk in chunks])
            
            # Prepare metadata
            metadatas = [
                {
                    "document_id": document_id,
                    "filename": filename,
                    "chunk_index": i,
                    "uploaded_by": uploaded_by,
                    "file_type": file_type
                }
                for i in range(len(chunks))
            ]
            
            # Store in vector database
            chunk_ids = [f"{document_id}_chunk_{i}" for i in range(len(chunks))]
            await vector_db.add_documents(
                texts=[chunk["text"] for chunk in chunks],
                embeddings=embeddings,
                metadatas=metadatas,
                ids=chunk_ids
            )
            
            total_chunks += len(chunks)
            print(f"   [OK] Ingested {len(chunks)} chunks")
            
        except Exception as e:
            print(f"   [ERROR] Error processing {filename}: {e}")
            import traceback
            traceback.print_exc()
            continue
    
    # Get final stats
    stats = await vector_db.get_collection_stats()
    print(f"\n[SUCCESS] Re-ingestion complete!")
    print(f"   Total chunks in vector DB: {stats.get('document_count', total_chunks)}")


async def get_all_documents_from_sqlite(db_path: str):
    """Get all documents from SQLite"""
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT id, filename, file_path, file_type, uploaded_by, uploaded_at, metadata
            FROM documents
            ORDER BY uploaded_at DESC
        """)
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


if __name__ == "__main__":
    asyncio.run(reingest_documents())

