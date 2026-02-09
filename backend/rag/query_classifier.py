"""
Query Classifier: Classifies audit document queries by type and intent
Enables role-based routing and specialized handling
"""
from typing import Dict, List, Optional, Tuple
import re
from enum import Enum


class QueryType(str, Enum):
    """Types of audit document queries"""
    FINANCIAL_METRICS = "financial_metrics"  # Revenue, profit, assets, etc.
    OPINION = "opinion"  # Auditor's opinion, opinion type
    FINDINGS = "findings"  # Audit findings, deficiencies, issues
    COMPLIANCE = "compliance"  # Compliance status, standards, regulations
    SUMMARY = "summary"  # Executive summary, overview
    KAM = "kam"  # Key Audit Matters
    DOCUMENT_METADATA = "document_metadata"  # Title, date, auditor name
    COMPARISON = "comparison"  # Compare periods, documents, metrics
    RISK = "risk"  # Risk assessment, risk factors
    RECOMMENDATIONS = "recommendations"  # Recommendations, actions required
    GENERAL = "general"  # General questions


class QueryClassifier:
    """
    Classifies queries to enable specialized handling:
    - Role-based routing
    - Query-specific prompts
    - Targeted retrieval strategies
    """
    
    # Financial metrics keywords
    FINANCIAL_KEYWORDS = [
        'revenue', 'sales', 'income', 'profit', 'loss', 'earnings',
        'assets', 'liabilities', 'equity', 'cash flow', 'balance sheet',
        'income statement', 'financial position', 'net income', 'gross profit',
        'operating income', 'ebitda', 'margin', 'ratio', 'percentage',
        'quarter', 'q1', 'q2', 'q3', 'q4', 'fiscal year', 'annual'
    ]
    
    # Opinion keywords
    OPINION_KEYWORDS = [
        'opinion', 'auditor opinion', 'unqualified', 'qualified', 'adverse',
        'disclaimer', 'clean opinion', 'modified opinion', 'audit conclusion'
    ]
    
    # Findings keywords
    FINDINGS_KEYWORDS = [
        'finding', 'deficiency', 'weakness', 'issue', 'problem', 'concern',
        'material weakness', 'significant deficiency', 'exception', 'non-compliance',
        'violation', 'breach', 'gap', 'shortcoming'
    ]
    
    # Compliance keywords
    COMPLIANCE_KEYWORDS = [
        'compliance', 'comply', 'standard', 'regulation', 'requirement',
        'gaap', 'ifrs', 'sox', 'sarbanes-oxley', 'hipaa', 'pci', 'gdpr',
        'regulatory', 'audit standard', 'accounting standard'
    ]
    
    # Summary keywords
    SUMMARY_KEYWORDS = [
        'summary', 'overview', 'summary of', 'executive summary', 'highlights',
        'key points', 'main points', 'brief', 'synopsis', 'abstract'
    ]
    
    # KAM keywords
    KAM_KEYWORDS = [
        'key audit matter', 'kam', 'critical audit matter', 'cam',
        'significant matter', 'important matter', 'key issue'
    ]
    
    # Comparison keywords
    COMPARISON_KEYWORDS = [
        'compare', 'comparison', 'versus', 'vs', 'difference', 'change',
        'trend', 'increase', 'decrease', 'growth', 'decline', 'year over year',
        'yoy', 'quarter over quarter', 'qoq', 'prior period', 'previous year'
    ]
    
    # Risk keywords
    RISK_KEYWORDS = [
        'risk', 'risky', 'risk factor', 'uncertainty', 'vulnerability',
        'threat', 'exposure', 'going concern', 'liquidity risk', 'credit risk',
        'operational risk', 'market risk'
    ]
    
    # Recommendations keywords
    RECOMMENDATIONS_KEYWORDS = [
        'recommendation', 'recommend', 'suggestion', 'action', 'should',
        'action required', 'improvement', 'enhancement', 'remedy', 'solution'
    ]
    
    def __init__(self):
        pass
    
    def classify(self, query: str, user_role: Optional[str] = None) -> Dict[str, any]:
        """
        Classify query and return classification with confidence
        Returns: {
            'type': QueryType,
            'confidence': float (0-1),
            'subtype': Optional[str],
            'entities': List[str],  # Extracted entities (dates, metrics, etc.)
            'role_specific': bool
        }
        """
        query_lower = query.lower().strip()
        
        # Check each query type
        classifications = []
        
        # Financial metrics
        financial_score = self._score_keywords(query_lower, self.FINANCIAL_KEYWORDS)
        if financial_score > 0:
            classifications.append((QueryType.FINANCIAL_METRICS, financial_score))
        
        # Opinion
        opinion_score = self._score_keywords(query_lower, self.OPINION_KEYWORDS)
        if opinion_score > 0:
            classifications.append((QueryType.OPINION, opinion_score))
        
        # Findings
        findings_score = self._score_keywords(query_lower, self.FINDINGS_KEYWORDS)
        if findings_score > 0:
            classifications.append((QueryType.FINDINGS, findings_score))
        
        # Compliance
        compliance_score = self._score_keywords(query_lower, self.COMPLIANCE_KEYWORDS)
        if compliance_score > 0:
            classifications.append((QueryType.COMPLIANCE, compliance_score))
        
        # Summary
        summary_score = self._score_keywords(query_lower, self.SUMMARY_KEYWORDS)
        if summary_score > 0:
            classifications.append((QueryType.SUMMARY, summary_score))
        
        # KAM
        kam_score = self._score_keywords(query_lower, self.KAM_KEYWORDS)
        if kam_score > 0:
            classifications.append((QueryType.KAM, kam_score))
        
        # Comparison
        comparison_score = self._score_keywords(query_lower, self.COMPARISON_KEYWORDS)
        if comparison_score > 0:
            classifications.append((QueryType.COMPARISON, comparison_score))
        
        # Risk
        risk_score = self._score_keywords(query_lower, self.RISK_KEYWORDS)
        if risk_score > 0:
            classifications.append((QueryType.RISK, risk_score))
        
        # Recommendations
        rec_score = self._score_keywords(query_lower, self.RECOMMENDATIONS_KEYWORDS)
        if rec_score > 0:
            classifications.append((QueryType.RECOMMENDATIONS, rec_score))
        
        # Document metadata (check last to avoid false positives)
        if any(keyword in query_lower for keyword in ['title', 'filename', 'name of document', 'what document', 'which document']):
            classifications.append((QueryType.DOCUMENT_METADATA, 0.8))
        
        # Determine primary type
        if classifications:
            # Sort by score (highest first)
            classifications.sort(key=lambda x: x[1], reverse=True)
            primary_type, confidence = classifications[0]
            
            # Check for multiple types (hybrid queries)
            if len(classifications) > 1 and classifications[1][1] > confidence * 0.7:
                # Hybrid query - use primary but note secondary
                secondary_type = classifications[1][0]
                subtype = f"{primary_type.value}_{secondary_type.value}"
            else:
                subtype = None
        else:
            primary_type = QueryType.GENERAL
            confidence = 0.5
            subtype = None
        
        # Extract entities
        entities = self._extract_entities(query)
        
        # Determine if role-specific
        role_specific = self._is_role_specific(query_lower, user_role)
        
        return {
            'type': primary_type,
            'confidence': min(confidence, 1.0),
            'subtype': subtype,
            'entities': entities,
            'role_specific': role_specific,
            'all_matches': [(t.value, s) for t, s in classifications[:3]]  # Top 3 matches
        }
    
    def _score_keywords(self, query: str, keywords: List[str]) -> float:
        """Score how well query matches keyword list"""
        matches = sum(1 for keyword in keywords if keyword in query)
        if matches == 0:
            return 0.0
        
        # Normalize score (more matches = higher score, but cap at 1.0)
        score = min(matches / max(len(keywords) * 0.1, 3), 1.0)
        
        # Boost if keyword appears at start of query
        if any(query.startswith(kw) for kw in keywords):
            score = min(score * 1.3, 1.0)
        
        return score
    
    def _extract_entities(self, query: str) -> List[str]:
        """Extract entities from query (dates, metrics, company names, etc.)"""
        entities = []
        
        # Extract dates
        date_patterns = [
            r'\d{4}',  # Year
            r'[A-Z][a-z]+\s+\d{1,2},?\s+\d{4}',  # Full date
            r'Q[1-4]\s+\d{4}',  # Quarter
        ]
        for pattern in date_patterns:
            matches = re.findall(pattern, query, re.IGNORECASE)
            entities.extend(matches)
        
        # Extract financial amounts
        amount_patterns = [
            r'\$[\d,]+(?:\.\d{2})?',
            r'[\d,]+(?:\.\d{2})?\s*(?:million|billion|thousand|M|B|K)',
        ]
        for pattern in amount_patterns:
            matches = re.findall(pattern, query, re.IGNORECASE)
            entities.extend(matches)
        
        # Extract percentages
        percent_matches = re.findall(r'\d+%', query)
        entities.extend(percent_matches)
        
        return list(set(entities))  # Remove duplicates
    
    def _is_role_specific(self, query: str, user_role: Optional[str]) -> bool:
        """Determine if query is specific to a role"""
        if not user_role:
            return False
        
        # Role-specific query patterns
        role_patterns = {
            'admin': ['all documents', 'all users', 'access', 'permission'],
            'auditor': ['audit procedure', 'testing', 'evidence', 'workpaper', 'audit trail'],
            'viewer': ['summary', 'overview', 'highlights', 'key points'],
        }
        
        patterns = role_patterns.get(user_role.lower(), [])
        return any(pattern in query for pattern in patterns)
    
    def get_retrieval_strategy(self, classification: Dict) -> Dict[str, any]:
        """
        Get retrieval strategy based on classification
        Returns strategy configuration for RAG engine
        """
        query_type = classification['type']
        
        strategies = {
            QueryType.FINANCIAL_METRICS: {
                'max_results': 3,
                'similarity_threshold': 0.65,
                'prefer_sections': ['financial statements', 'balance sheet', 'income statement'],
                'include_tables': True,
            },
            QueryType.OPINION: {
                'max_results': 2,
                'similarity_threshold': 0.7,
                'prefer_sections': ['opinion', 'auditor\'s opinion', 'basis for opinion'],
                'include_tables': False,
            },
            QueryType.FINDINGS: {
                'max_results': 5,
                'similarity_threshold': 0.6,
                'prefer_sections': ['findings', 'deficiencies', 'issues', 'management letter'],
                'include_tables': False,
            },
            QueryType.COMPLIANCE: {
                'max_results': 4,
                'similarity_threshold': 0.65,
                'prefer_sections': ['compliance', 'regulatory', 'standards'],
                'include_tables': False,
            },
            QueryType.SUMMARY: {
                'max_results': 3,
                'similarity_threshold': 0.6,
                'prefer_sections': ['executive summary', 'overview', 'introduction'],
                'include_tables': False,
            },
            QueryType.KAM: {
                'max_results': 3,
                'similarity_threshold': 0.7,
                'prefer_sections': ['key audit matters', 'kam', 'critical audit matters'],
                'include_tables': False,
            },
            QueryType.COMPARISON: {
                'max_results': 5,
                'similarity_threshold': 0.6,
                'prefer_sections': None,  # Need multiple documents
                'include_tables': True,
            },
            QueryType.RISK: {
                'max_results': 4,
                'similarity_threshold': 0.65,
                'prefer_sections': ['risk', 'risk assessment', 'uncertainties'],
                'include_tables': False,
            },
            QueryType.RECOMMENDATIONS: {
                'max_results': 4,
                'similarity_threshold': 0.6,
                'prefer_sections': ['recommendations', 'suggestions', 'actions'],
                'include_tables': False,
            },
            QueryType.DOCUMENT_METADATA: {
                'max_results': 1,
                'similarity_threshold': 0.3,
                'prefer_sections': None,
                'include_tables': False,
            },
            QueryType.GENERAL: {
                'max_results': 3,
                'similarity_threshold': 0.6,
                'prefer_sections': None,
                'include_tables': False,
            },
        }
        
        return strategies.get(query_type, strategies[QueryType.GENERAL])
