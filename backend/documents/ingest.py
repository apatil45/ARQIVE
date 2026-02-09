"""
Document ingestion pipeline
"""
import os
import uuid
import aiofiles
from fastapi import UploadFile
from typing import Dict, Optional
from io import BytesIO

from config import settings
from db.vector import VectorDB
from db.sqlite import SQLiteDB
from rag.chunker import Chunker
from rag.embeddings import EmbeddingModel
from rag.audit_chunker import AuditChunker
from rag.audit_metadata import AuditMetadataExtractor


async def ingest_document(
    file: UploadFile,
    username: str,
    vector_db: VectorDB,
    sqlite_db: SQLiteDB,
    content_type: Optional[str] = None
) -> str:
    """
    Ingest a document: save file, extract text, chunk, embed, and store
    Supports both S3 and local filesystem storage
    """
    # Generate document ID
    document_id = str(uuid.uuid4())
    
    # Read file content once
    content = await file.read()
    file_size = len(content)
    
    # Sanitize filename to prevent path traversal
    safe_filename = os.path.basename(file.filename) if file.filename else "unnamed"
    safe_filename = "".join(c for c in safe_filename if c.isalnum() or c in "._- ")
    if not safe_filename:
        safe_filename = "document"
    
    # Determine storage location and file path/key
    file_storage_path = None  # Will be set based on storage type
    
    if settings.USE_S3 and settings.S3_BUCKET_NAME:
        # Use S3 storage
        from storage.s3_storage import S3Storage
        storage = S3Storage()
        
        # S3 key: documents/{document_id}/{filename}
        s3_key = f"documents/{document_id}/{safe_filename}"
        
        # Upload to S3
        await storage.upload_file(
            file_content=content,
            s3_key=s3_key,
            content_type=content_type or file.content_type
        )
        
        file_storage_path = s3_key  # Store S3 key instead of local path
        
        # For text extraction, we need the file locally temporarily
        # Save to temp location for processing
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(safe_filename)[1]) as temp_file:
            temp_file.write(content)
            temp_file_path = temp_file.name
        
        try:
            # Extract text from temp file
            text = await extract_text(temp_file_path, content_type or file.content_type or "unknown")
        finally:
            # Clean up temp file
            try:
                os.unlink(temp_file_path)
            except:
                pass
    else:
        # Use local filesystem storage
        # Create upload directory if it doesn't exist
        os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
        
        # Save file with sanitized filename
        file_path = os.path.join(settings.UPLOAD_DIR, f"{document_id}_{safe_filename}")
        # Ensure path is within upload directory (prevent path traversal)
        file_path = os.path.normpath(file_path)
        if not file_path.startswith(os.path.normpath(settings.UPLOAD_DIR)):
            raise ValueError("Invalid file path")
        
        async with aiofiles.open(file_path, 'wb') as f:
            await f.write(content)
        
        file_storage_path = file_path
        
        # Extract text based on file type (use provided content_type or file.content_type)
        text = await extract_text(file_path, content_type or file.content_type or "unknown")
    
    if not text or len(text.strip()) == 0:
        raise ValueError("Could not extract text from document")
    
    # Chunk the text
    chunker = Chunker()
    chunks = chunker.chunk_text(text)
    
    # Generate embeddings
    embedding_model = EmbeddingModel()
    embeddings = await embedding_model.embed_batch([chunk["text"] for chunk in chunks])
    
    # Prepare metadata for each chunk (enhance with audit metadata)
    metadatas = []
    for i, chunk in enumerate(chunks):
        chunk_metadata = {
            "document_id": document_id,
            "filename": file.filename,
            "chunk_index": i,
            "uploaded_by": username,
            "file_type": file.content_type
        }
        
        # Add audit-specific metadata if available
        if isinstance(chunk, dict):
            # Audit chunker returns dict with additional fields
            if 'section' in chunk:
                chunk_metadata['section'] = chunk['section']
            if 'section_hierarchy' in chunk:
                chunk_metadata['section_hierarchy'] = chunk['section_hierarchy']
            if 'metadata' in chunk:
                chunk_metadata['chunk_metadata'] = chunk['metadata']
        
        metadatas.append(chunk_metadata)
    
    # Store in vector database and SQLite with transaction-like behavior
    # Use transaction manager for atomic operations
    chunk_ids = [f"{document_id}_chunk_{i}" for i in range(len(chunks))]
    
    # Use transaction context manager for safe ingestion
    from utils.transactions import document_ingestion_transaction
    
    async with document_ingestion_transaction(
        vector_db=vector_db,
        sqlite_db=sqlite_db,
        document_id=document_id,
        chunk_ids=chunk_ids,
        file_storage_path=file_storage_path
    ) as tx:
        # Store in vector database first
        await vector_db.add_documents(
            texts=[chunk["text"] for chunk in chunks],
            embeddings=embeddings,
            metadatas=metadatas,
            ids=chunk_ids
        )
        
        # Store document metadata in SQLite (enhanced with audit metadata)
        document_metadata = {
            "chunk_count": len(chunks),
            "file_size": file_size,
            "storage_type": "s3" if settings.USE_S3 else "local",
            "audit_metadata": audit_metadata  # Add extracted audit metadata
        }
        
        await sqlite_db.add_document(
            document_id=document_id,
            filename=file.filename,
            file_path=file_storage_path,  # S3 key or local path
            file_type=content_type or file.content_type or "unknown",
            uploaded_by=username,
            metadata=document_metadata
        )
        
        return document_id


async def extract_text(file_path: str, content_type: str) -> str:
    """
    Extract text from document based on file type
    Uses PyPDF2 for PDF, python-docx for DOCX, simple read for TXT
    Includes proper error handling for corrupted files
    """
    if content_type == "text/plain":
        try:
            async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                return await f.read()
        except UnicodeDecodeError:
            # Try with different encoding
            async with aiofiles.open(file_path, 'r', encoding='latin-1') as f:
                return await f.read()
        except Exception as e:
            raise ValueError(f"Failed to read text file: {str(e)}")
            
    elif content_type == "application/pdf":
        # Use PyPDF2 for PDF
        import PyPDF2
        text_parts = []
        try:
            with open(file_path, 'rb') as f:
                pdf_reader = PyPDF2.PdfReader(f)
                # Check if PDF is encrypted
                if pdf_reader.is_encrypted:
                    raise ValueError("PDF is password-protected and cannot be processed")
                
                for page in pdf_reader.pages:
                    try:
                        text = page.extract_text()
                        if text:
                            text_parts.append(text)
                    except Exception as e:
                        # Skip corrupted pages but continue
                        import warnings
                        warnings.warn(f"Failed to extract text from page: {e}", UserWarning)
                        continue
                        
            if not text_parts:
                raise ValueError("No text could be extracted from PDF")
            return "\n\n".join(text_parts)
        except PyPDF2.errors.PdfReadError as e:
            raise ValueError(f"PDF file is corrupted or invalid: {str(e)}")
        except Exception as e:
            raise ValueError(f"Failed to extract text from PDF: {str(e)}")
            
    elif content_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        # Use python-docx for DOCX
        try:
            from docx import Document
            doc = Document(file_path)
            paragraphs = [para.text for para in doc.paragraphs if para.text.strip()]
            if not paragraphs:
                raise ValueError("Document appears to be empty")
            return "\n\n".join(paragraphs)
        except Exception as e:
            raise ValueError(f"Failed to extract text from DOCX: {str(e)}")
    else:
        raise ValueError(f"Unsupported file type: {content_type}")

