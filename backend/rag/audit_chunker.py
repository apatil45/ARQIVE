"""
Audit-Aware Chunker: Preserves document structure for audit reports
Industry-standard chunking that maintains hierarchy, sections, tables, and metadata
"""
from typing import List, Dict, Any, Optional, Tuple
import re
import tiktoken
from config import settings


class AuditChunker:
    """
    Specialized chunker for audit documents that:
    1. Preserves document structure (sections, headers, tables)
    2. Maintains context hierarchy (report > section > subsection > content
    3. Preserves metadata (page numbers, dates, auditor names)
    4. Handles financial tables and structured data
    """
    
    # Audit document section patterns
    SECTION_PATTERNS = [
        r'^(?:Section|Part)\s+\d+[\.:]?\s+',  # "Section 1:" or "Part 1."
        r'^[A-Z][A-Z\s]{10,}$',  # ALL CAPS headers (common in audit reports)
        r'^\d+\.\s+[A-Z]',  # Numbered sections "1. Introduction"
        r'^[IVX]+\.\s+[A-Z]',  # Roman numerals "I. Executive Summary"
        r'^[A-Z][a-z]+\s+[A-Z][a-z]+:',  # Title Case Headers:
    ]
    
    # Audit-specific section keywords
    AUDIT_SECTIONS = [
        'executive summary', 'management letter', 'auditor\'s opinion', 'opinion',
        'basis for opinion', 'management\'s responsibility', 'auditor\'s responsibility',
        'financial statements', 'balance sheet', 'income statement', 'cash flow',
        'notes to financial statements', 'key audit matters', 'kam', 'findings',
        'recommendations', 'internal controls', 'compliance', 'risk assessment',
        'scope of audit', 'audit procedures', 'materiality', 'going concern',
        'subsequent events', 'related party transactions', 'contingencies'
    ]
    
    # Financial metrics patterns
    FINANCIAL_PATTERNS = [
        r'\$[\d,]+(?:\.\d{2})?',  # Currency amounts
        r'\d+%',  # Percentages
        r'(?:revenue|profit|loss|assets|liabilities|equity)\s*[:=]\s*\$?[\d,]+',
        r'(?:Q[1-4]|quarter|year|fiscal)\s+\d{4}',  # Time periods
    ]
    
    def __init__(self):
        try:
            self.encoding = tiktoken.get_encoding("cl100k_base")
        except:
            self.encoding = None
    
    def _count_tokens(self, text: str) -> int:
        """Count tokens in text"""
        if self.encoding:
            return len(self.encoding.encode(text))
        return len(text) // 4
    
    def _detect_section(self, line: str) -> Optional[Tuple[str, str]]:
        """
        Detect if a line is a section header
        Returns (section_type, section_title) or None
        """
        line_stripped = line.strip()
        if not line_stripped:
            return None
        
        # Check for audit-specific sections
        line_lower = line_stripped.lower()
        for section_keyword in self.AUDIT_SECTIONS:
            if section_keyword in line_lower:
                return ('audit_section', line_stripped)
        
        # Check for pattern-based sections
        for pattern in self.SECTION_PATTERNS:
            if re.match(pattern, line_stripped):
                return ('section_header', line_stripped)
        
        # Check if line looks like a header (short, title case, no punctuation at end)
        if (len(line_stripped) < 100 and 
            line_stripped[0].isupper() and 
            not line_stripped.endswith(('.', ':', ';', ',')) and
            len(line_stripped.split()) < 15):
            return ('potential_header', line_stripped)
        
        return None
    
    def _extract_metadata(self, text: str) -> Dict[str, Any]:
        """
        Extract audit-specific metadata from text
        """
        metadata = {
            'has_financial_data': False,
            'has_tables': False,
            'sections': [],
            'audit_period': None,
            'auditor_name': None,
        }
        
        # Detect financial data
        for pattern in self.FINANCIAL_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                metadata['has_financial_data'] = True
                break
        
        # Detect tables (multiple aligned columns or tab-separated)
        if re.search(r'\t.*\t|\s{3,}.*\s{3,}', text):
            metadata['has_tables'] = True
        
        # Extract audit period
        period_match = re.search(r'(?:for\s+the\s+)?(?:year|period|quarter|fiscal\s+year)\s+ended?\s+([A-Z][a-z]+\s+\d{1,2},?\s+\d{4})', text, re.IGNORECASE)
        if period_match:
            metadata['audit_period'] = period_match.group(1)
        
        # Extract auditor name (common patterns)
        auditor_match = re.search(r'(?:audited\s+by|prepared\s+by|auditor[:\s]+)([A-Z][a-z]+\s+(?:LLP|LLC|Inc\.|Ltd\.|&|and)\s+[A-Z][a-z]+)', text, re.IGNORECASE)
        if auditor_match:
            metadata['auditor_name'] = auditor_match.group(1)
        
        return metadata
    
    def _chunk_with_structure(
        self, 
        text: str, 
        preserve_sections: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Chunk text while preserving document structure
        """
        chunks = []
        lines = text.split('\n')
        
        current_section = None
        current_chunk_lines = []
        current_tokens = 0
        section_hierarchy = []  # Track section nesting
        
        for line_num, line in enumerate(lines):
            line_tokens = self._count_tokens(line)
            
            # Detect section headers
            section_info = self._detect_section(line) if preserve_sections else None
            
            if section_info:
                section_type, section_title = section_info
                
                # Save current chunk if it has content
                if current_chunk_lines and current_tokens > 0:
                    chunk_text = '\n'.join(current_chunk_lines)
                    chunks.append({
                        'text': chunk_text,
                        'token_count': current_tokens,
                        'section': current_section,
                        'section_hierarchy': section_hierarchy.copy(),
                        'line_start': line_num - len(current_chunk_lines),
                        'line_end': line_num - 1
                    })
                    current_chunk_lines = []
                    current_tokens = 0
                
                # Update section context
                if section_type == 'audit_section':
                    # Major audit section - reset hierarchy
                    section_hierarchy = [section_title]
                else:
                    # Subsection - add to hierarchy
                    if len(section_hierarchy) < 3:  # Limit depth
                        section_hierarchy.append(section_title)
                    else:
                        section_hierarchy[-1] = section_title
                
                current_section = section_title
                # Include header in next chunk
                current_chunk_lines.append(line)
                current_tokens += line_tokens
                continue
            
            # Add line to current chunk
            current_chunk_lines.append(line)
            current_tokens += line_tokens
            
            # Check if chunk is full
            if current_tokens >= settings.CHUNK_SIZE:
                # Try to break at sentence boundary
                chunk_text = '\n'.join(current_chunk_lines)
                
                # Find last sentence boundary
                sentences = re.split(r'([.!?]+\s+)', chunk_text)
                if len(sentences) > 2:
                    # Split at sentence boundary
                    split_point = len(''.join(sentences[:-2]))
                    first_part = chunk_text[:split_point].strip()
                    second_part = chunk_text[split_point:].strip()
                    
                    if first_part:
                        chunks.append({
                            'text': first_part,
                            'token_count': self._count_tokens(first_part),
                            'section': current_section,
                            'section_hierarchy': section_hierarchy.copy(),
                            'line_start': line_num - len(current_chunk_lines),
                            'line_end': line_num
                        })
                    
                    # Start new chunk with remainder
                    current_chunk_lines = [second_part] if second_part else []
                    current_tokens = self._count_tokens(second_part) if second_part else 0
                else:
                    # No good sentence boundary, just save chunk
                    chunks.append({
                        'text': chunk_text,
                        'token_count': current_tokens,
                        'section': current_section,
                        'section_hierarchy': section_hierarchy.copy(),
                        'line_start': line_num - len(current_chunk_lines),
                        'line_end': line_num
                    })
                    current_chunk_lines = []
                    current_tokens = 0
        
        # Add final chunk
        if current_chunk_lines:
            chunk_text = '\n'.join(current_chunk_lines)
            chunks.append({
                'text': chunk_text,
                'token_count': self._count_tokens(chunk_text),
                'section': current_section,
                'section_hierarchy': section_hierarchy.copy(),
                'line_start': len(lines) - len(current_chunk_lines),
                'line_end': len(lines) - 1
            })
        
        # Add overlap between chunks (preserve context)
        overlapped_chunks = []
        for i, chunk in enumerate(chunks):
            chunk_text = chunk['text']
            
            # Add overlap from previous chunk
            if i > 0 and settings.CHUNK_OVERLAP > 0:
                prev_chunk = chunks[i - 1]
                prev_text = prev_chunk['text']
                prev_sentences = re.split(r'([.!?]+\s+)', prev_text)
                
                # Take last N sentences for overlap
                overlap_tokens = 0
                overlap_sentences = []
                for sent in reversed(prev_sentences):
                    sent_tokens = self._count_tokens(sent)
                    if overlap_tokens + sent_tokens <= settings.CHUNK_OVERLAP:
                        overlap_sentences.insert(0, sent)
                        overlap_tokens += sent_tokens
                    else:
                        break
                
                if overlap_sentences:
                    overlap_text = ''.join(overlap_sentences)
                    chunk_text = overlap_text + '\n\n' + chunk_text
            
            # Extract metadata for this chunk
            chunk_metadata = self._extract_metadata(chunk_text)
            
            overlapped_chunks.append({
                'text': chunk_text,
                'token_count': self._count_tokens(chunk_text),
                'section': chunk.get('section'),
                'section_hierarchy': chunk.get('section_hierarchy', []),
                'line_start': chunk.get('line_start'),
                'line_end': chunk.get('line_end'),
                'metadata': chunk_metadata
            })
        
        return overlapped_chunks
    
    def chunk_text(self, text: str, preserve_structure: bool = True) -> List[Dict[str, Any]]:
        """
        Main chunking method
        """
        if not text or not text.strip():
            return []
        
        if preserve_structure:
            return self._chunk_with_structure(text, preserve_sections=True)
        else:
            # Fallback to simple chunking
            from rag.chunker import Chunker
            simple_chunker = Chunker()
            return simple_chunker.chunk_text(text)
