"""
Text chunking utilities
"""
from typing import List, Dict, Any
import tiktoken  # For token counting
import re

from config import settings

# Constants
TOKEN_CHAR_RATIO = 4  # Approximate ratio: 1 token ≈ 4 characters


class Chunker:
    """Text chunker with token-based splitting"""
    
    def __init__(self):
        # Use cl100k_base encoding (GPT-4 style) for token counting
        try:
            self.encoding = tiktoken.get_encoding("cl100k_base")
        except:
            # Fallback to approximate if tiktoken not available
            self.encoding = None
    
    def _count_tokens(self, text: str) -> int:
        """Count tokens in text"""
        if self.encoding:
            return len(self.encoding.encode(text))
        # Approximate: 1 token ≈ 4 characters
        return len(text) // TOKEN_CHAR_RATIO
    
    def chunk_text(self, text: str) -> List[Dict[str, Any]]:
        """
        Split text into chunks with overlap
        Returns list of dicts with 'text' and 'token_count'
        Improved sentence splitting to handle abbreviations and multiple sentence endings
        """
        chunks = []
        
        if not text or not text.strip():
            return chunks
        
        # Improved sentence splitting using regex to handle:
        # - Periods (but not abbreviations like "Dr.", "Mr.", "U.S.A.")
        # - Question marks
        # - Exclamation marks
        import re
        # Pattern: sentence ending followed by space and capital letter, or end of string
        # Excludes common abbreviations
        sentence_pattern = r'(?<=[.!?])\s+(?=[A-Z])|(?<=[.!?])(?=\s*$)'
        # Split but keep the delimiters by using lookahead/lookbehind
        sentences = re.split(sentence_pattern, text)
        # Filter out empty strings and clean up
        sentences = [s.strip() for s in sentences if s.strip()]
        
        # If regex splitting didn't work well, fall back to simple split
        if len(sentences) < 2:
            # Fallback: split on sentence endings
            sentences = re.split(r'([.!?]+)\s+', text)
            # Recombine sentences with their punctuation
            combined = []
            for i in range(0, len(sentences) - 1, 2):
                if i + 1 < len(sentences):
                    combined.append(sentences[i] + sentences[i + 1])
                else:
                    combined.append(sentences[i])
            sentences = [s.strip() for s in combined if s.strip()]
        
        # If still no good splits, split by newlines or just chunk by size
        if len(sentences) < 2:
            # Last resort: split by paragraphs or fixed size
            paragraphs = text.split('\n\n')
            if len(paragraphs) > 1:
                sentences = paragraphs
            else:
                # Chunk by character count as fallback
                chunk_size_chars = settings.CHUNK_SIZE * 4  # Approximate
                for i in range(0, len(text), chunk_size_chars):
                    chunk = text[i:i + chunk_size_chars]
                    if chunk.strip():
                        chunks.append({
                            "text": chunk.strip(),
                            "token_count": self._count_tokens(chunk)
                        })
                return chunks
        
        current_chunk = []
        current_tokens = 0
        
        for sentence in sentences:
            sentence_tokens = self._count_tokens(sentence)
            
            if current_tokens + sentence_tokens > settings.CHUNK_SIZE and current_chunk:
                # Save current chunk
                chunk_text = ' '.join(current_chunk)
                chunks.append({
                    "text": chunk_text,
                    "token_count": current_tokens
                })
                
                # Start new chunk with overlap (keep last few sentences)
                overlap_tokens = 0
                overlap_sentences = []
                for s in reversed(current_chunk):
                    s_tokens = self._count_tokens(s)
                    if overlap_tokens + s_tokens <= settings.CHUNK_OVERLAP:
                        overlap_sentences.insert(0, s)
                        overlap_tokens += s_tokens
                    else:
                        break
                
                current_chunk = overlap_sentences + [sentence]
                current_tokens = sum(self._count_tokens(s) for s in current_chunk)
            else:
                current_chunk.append(sentence)
                current_tokens += sentence_tokens
        
        # Add final chunk
        if current_chunk:
            chunk_text = ' '.join(current_chunk)
            chunks.append({
                "text": chunk_text,
                "token_count": current_tokens
            })
        
        return chunks

