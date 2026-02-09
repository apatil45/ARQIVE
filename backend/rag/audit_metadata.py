"""
Audit Metadata Extractor: Extracts structured metadata from audit documents
Industry-standard extraction for audit reports, financial statements, and compliance documents
"""
from typing import Dict, List, Optional, Any
import re
from datetime import datetime


class AuditMetadataExtractor:
    """
    Extracts audit-specific metadata from documents:
    - Audit period, dates
    - Auditor information
    - Opinion type (unqualified, qualified, adverse, disclaimer)
    - Key Audit Matters (KAMs)
    - Financial metrics
    - Document structure
    - Compliance information
    """
    
    # Opinion types
    OPINION_TYPES = {
        'unqualified': ['unqualified opinion', 'clean opinion', 'unmodified opinion'],
        'qualified': ['qualified opinion', 'except for', 'subject to'],
        'adverse': ['adverse opinion', 'does not present fairly'],
        'disclaimer': ['disclaimer of opinion', 'unable to express', 'scope limitation']
    }
    
    # Financial statement types
    FINANCIAL_STATEMENTS = [
        'balance sheet', 'statement of financial position',
        'income statement', 'statement of operations', 'profit and loss', 'p&l',
        'cash flow statement', 'statement of cash flows',
        'statement of changes in equity', 'statement of shareholders equity',
        'notes to financial statements', 'footnotes'
    ]
    
    def __init__(self):
        pass
    
    def extract_document_metadata(self, text: str, filename: str) -> Dict[str, Any]:
        """
        Extract comprehensive metadata from audit document
        """
        metadata = {
            'document_type': self._detect_document_type(text, filename),
            'audit_period': self._extract_audit_period(text),
            'report_date': self._extract_report_date(text),
            'auditor': self._extract_auditor(text),
            'auditee': self._extract_auditee(text, filename),
            'opinion_type': self._extract_opinion_type(text),
            'key_audit_matters': self._extract_kams(text),
            'financial_statements': self._extract_financial_statements(text),
            'financial_metrics': self._extract_financial_metrics(text),
            'sections': self._extract_sections(text),
            'compliance_standards': self._extract_compliance_standards(text),
            'industry': self._detect_industry(text, filename),
            'has_findings': self._has_findings(text),
            'has_recommendations': self._has_recommendations(text),
        }
        
        return metadata
    
    def _detect_document_type(self, text: str, filename: str) -> str:
        """Detect type of audit document"""
        text_lower = text.lower()
        filename_lower = filename.lower()
        
        if any(term in text_lower for term in ['independent auditor', 'auditor\'s report', 'audit report']):
            return 'audit_report'
        elif any(term in text_lower for term in ['financial statements', 'balance sheet', 'income statement']):
            return 'financial_statements'
        elif any(term in text_lower for term in ['management letter', 'management representation']):
            return 'management_letter'
        elif any(term in text_lower for term in ['internal control', 'sox', 'sarbanes-oxley']):
            return 'internal_control_report'
        elif 'compliance' in text_lower:
            return 'compliance_report'
        else:
            return 'general_audit_document'
    
    def _extract_audit_period(self, text: str) -> Optional[str]:
        """Extract audit period (e.g., "year ended December 31, 2023")"""
        patterns = [
            r'(?:for\s+the\s+)?(?:year|period|fiscal\s+year|twelve\s+months)\s+ended?\s+([A-Z][a-z]+\s+\d{1,2},?\s+\d{4})',
            r'(?:year|period)\s+ended?\s+([A-Z][a-z]+\s+\d{1,2},?\s+\d{4})',
            r'(?:Q[1-4]|quarter)\s+(\d{4})',
            r'(\d{4})\s+(?:annual|year)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1) if match.lastindex else match.group(0)
        
        return None
    
    def _extract_report_date(self, text: str) -> Optional[str]:
        """Extract report date"""
        patterns = [
            r'(?:dated|as\s+of|report\s+date)[:\s]+([A-Z][a-z]+\s+\d{1,2},?\s+\d{4})',
            r'([A-Z][a-z]+\s+\d{1,2},?\s+\d{4})\s*(?:\.|,|\n)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return None
    
    def _extract_auditor(self, text: str) -> Optional[str]:
        """Extract auditor firm name"""
        patterns = [
            r'(?:audited\s+by|prepared\s+by|auditor[:\s]+)([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*(?:\s+(?:LLP|LLC|Inc\.|Ltd\.|&|and|CPA|P\.C\.))+)',
            r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+(?:LLP|LLC|Inc\.|Ltd\.))\s+(?:has\s+)?audited',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        return None
    
    def _extract_auditee(self, text: str, filename: str) -> Optional[str]:
        """Extract auditee (company/organization being audited)"""
        # Try from filename first
        filename_clean = re.sub(r'[._-]', ' ', filename)
        
        # Common patterns in text
        patterns = [
            r'(?:audit\s+of|financial\s+statements\s+of|report\s+on)\s+([A-Z][a-zA-Z\s&,]+(?:Inc\.|LLC|Corp\.|Ltd\.|Company)?)',
            r'([A-Z][a-zA-Z\s&,]+(?:Inc\.|LLC|Corp\.|Ltd\.|Company))\s+(?:and\s+)?(?:and\s+)?(?:its\s+)?(?:subsidiaries|affiliates)?',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1).strip()
        
        return None
    
    def _extract_opinion_type(self, text: str) -> Optional[str]:
        """Extract auditor's opinion type"""
        text_lower = text.lower()
        
        for opinion_type, keywords in self.OPINION_TYPES.items():
            if any(keyword in text_lower for keyword in keywords):
                return opinion_type
        
        return None
    
    def _extract_kams(self, text: str) -> List[str]:
        """Extract Key Audit Matters (KAMs)"""
        kams = []
        
        # Look for KAM section
        kam_pattern = r'(?:key\s+audit\s+matters?|kam)(?:\s+and\s+other\s+matters?)?[:\s]+(.*?)(?=\n\n[A-Z]|\n\s*[A-Z][a-z]+\s+[A-Z]|$)'
        kam_section = re.search(kam_pattern, text, re.IGNORECASE | re.DOTALL)
        
        if kam_section:
            kam_text = kam_section.group(1)
            # Extract individual KAMs (numbered or bulleted)
            kam_items = re.split(r'(?:\d+\.|\*|\-)\s+', kam_text)
            kams = [item.strip() for item in kam_items if item.strip() and len(item.strip()) > 20]
        
        return kams[:10]  # Limit to 10 KAMs
    
    def _extract_financial_statements(self, text: str) -> List[str]:
        """Extract which financial statements are included"""
        found_statements = []
        text_lower = text.lower()
        
        for statement in self.FINANCIAL_STATEMENTS:
            if statement in text_lower:
                found_statements.append(statement)
        
        return found_statements
    
    def _extract_financial_metrics(self, text: str) -> Dict[str, Any]:
        """Extract key financial metrics"""
        metrics = {
            'revenue': None,
            'net_income': None,
            'total_assets': None,
            'total_liabilities': None,
            'equity': None,
        }
        
        # Patterns for common metrics
        patterns = {
            'revenue': r'(?:revenue|sales|total\s+revenue)[:\s\$]+\s*([\d,]+(?:\.\d{2})?)',
            'net_income': r'(?:net\s+income|net\s+profit|earnings)[:\s\$]+\s*([\d,]+(?:\.\d{2})?)',
            'total_assets': r'(?:total\s+assets)[:\s\$]+\s*([\d,]+(?:\.\d{2})?)',
            'total_liabilities': r'(?:total\s+liabilities)[:\s\$]+\s*([\d,]+(?:\.\d{2})?)',
            'equity': r'(?:total\s+equity|shareholders?\s+equity)[:\s\$]+\s*([\d,]+(?:\.\d{2})?)',
        }
        
        for metric, pattern in patterns.items():
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    value_str = match.group(1).replace(',', '')
                    metrics[metric] = float(value_str)
                except:
                    pass
        
        return metrics
    
    def _extract_sections(self, text: str) -> List[str]:
        """Extract major sections from document"""
        sections = []
        
        # Look for section headers (all caps, numbered, etc.)
        section_patterns = [
            r'^(?:Section|Part)\s+\d+[\.:]?\s+([A-Z][^\n]{5,50})',
            r'^[A-Z][A-Z\s]{10,}$',
            r'^\d+\.\s+([A-Z][^\n]{5,50})',
        ]
        
        lines = text.split('\n')
        for line in lines[:100]:  # Check first 100 lines
            line_stripped = line.strip()
            if len(line_stripped) > 10 and len(line_stripped) < 100:
                for pattern in section_patterns:
                    if re.match(pattern, line_stripped):
                        sections.append(line_stripped)
                        break
        
        return sections[:20]  # Limit to 20 sections
    
    def _extract_compliance_standards(self, text: str) -> List[str]:
        """Extract compliance standards mentioned"""
        standards = []
        text_lower = text.lower()
        
        standard_patterns = [
            r'(?:gaap|generally\s+accepted\s+accounting\s+principles)',
            r'(?:ifrs|international\s+financial\s+reporting\s+standards)',
            r'(?:pcaob|public\s+company\s+accounting\s+oversight\s+board)',
            r'(?:sox|sarbanes-oxley)',
            r'(?:hipaa|health\s+insurance\s+portability)',
            r'(?:pci\s+dss|payment\s+card\s+industry)',
            r'(?:gdpr|general\s+data\s+protection\s+regulation)',
        ]
        
        for pattern in standard_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                standards.append(match.group(0).upper())
        
        return list(set(standards))  # Remove duplicates
    
    def _detect_industry(self, text: str, filename: str) -> Optional[str]:
        """Detect industry from document"""
        text_lower = text.lower()
        filename_lower = filename.lower()
        
        industry_keywords = {
            'healthcare': ['hospital', 'healthcare', 'medical', 'patient', 'hipaa', 'pharmacy'],
            'banking': ['bank', 'financial institution', 'deposit', 'loan', 'credit', 'federal reserve'],
            'finance': ['investment', 'securities', 'trading', 'portfolio', 'asset management'],
            'insurance': ['insurance', 'premium', 'claim', 'underwriting', 'policy'],
            'manufacturing': ['manufacturing', 'production', 'factory', 'inventory'],
            'retail': ['retail', 'store', 'merchandise', 'sales'],
        }
        
        for industry, keywords in industry_keywords.items():
            if any(keyword in text_lower or keyword in filename_lower for keyword in keywords):
                return industry
        
        return None
    
    def _has_findings(self, text: str) -> bool:
        """Check if document contains audit findings"""
        findings_keywords = [
            'finding', 'deficiency', 'weakness', 'non-compliance',
            'material weakness', 'significant deficiency', 'exception'
        ]
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in findings_keywords)
    
    def _has_recommendations(self, text: str) -> bool:
        """Check if document contains recommendations"""
        rec_keywords = ['recommendation', 'suggest', 'should', 'recommend', 'action required']
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in rec_keywords)
