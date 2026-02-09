"""
Audit-Specific Prompts: Specialized prompts for different query types and roles
Industry-standard prompts optimized for audit document analysis
"""
from typing import Dict, List, Optional
from rag.query_classifier import QueryType


class AuditPromptBuilder:
    """
    Builds specialized prompts for audit document queries
    Tailored for different query types, roles, and contexts
    """
    
    def __init__(self):
        pass
    
    def build_prompt(
        self,
        query: str,
        context: str,
        query_type: QueryType,
        user_role: Optional[str] = None,
        document_metadata: Optional[Dict] = None
    ) -> str:
        """
        Build specialized prompt based on query type and role
        """
        if query_type == QueryType.FINANCIAL_METRICS:
            return self._financial_metrics_prompt(query, context, document_metadata)
        elif query_type == QueryType.OPINION:
            return self._opinion_prompt(query, context, document_metadata)
        elif query_type == QueryType.FINDINGS:
            return self._findings_prompt(query, context, user_role, document_metadata)
        elif query_type == QueryType.COMPLIANCE:
            return self._compliance_prompt(query, context, document_metadata)
        elif query_type == QueryType.SUMMARY:
            return self._summary_prompt(query, context, user_role, document_metadata)
        elif query_type == QueryType.KAM:
            return self._kam_prompt(query, context, document_metadata)
        elif query_type == QueryType.COMPARISON:
            return self._comparison_prompt(query, context, document_metadata)
        elif query_type == QueryType.RISK:
            return self._risk_prompt(query, context, document_metadata)
        elif query_type == QueryType.RECOMMENDATIONS:
            return self._recommendations_prompt(query, context, document_metadata)
        elif query_type == QueryType.DOCUMENT_METADATA:
            return self._metadata_prompt(query, context, document_metadata)
        else:
            return self._general_prompt(query, context, user_role, document_metadata)
    
    def _financial_metrics_prompt(self, query: str, context: str, metadata: Optional[Dict]) -> str:
        """Prompt for financial metrics queries"""
        metadata_str = self._format_metadata(metadata)
        
        return f"""You are a financial analysis assistant specializing in audit reports. Extract precise financial information from the provided context.

{metadata_str}

Context from Audit Documents:
{context}

Question: {query}

Instructions:
1. Identify the specific financial metric(s) requested (revenue, profit, assets, etc.)
2. Extract the EXACT numerical values from the context
3. Include the time period (year, quarter) for the metric
4. If multiple values exist, specify which document/section they come from
5. Format numbers clearly (e.g., $1,234,567 or 1.23M)
6. If the metric is not found, state: "The requested financial metric is not available in the provided documents."
7. Do NOT include random text - only provide the specific metric requested

Answer:"""
    
    def _opinion_prompt(self, query: str, context: str, metadata: Optional[Dict]) -> str:
        """Prompt for auditor's opinion queries"""
        metadata_str = self._format_metadata(metadata)
        
        return f"""You are an audit report analysis assistant. Extract information about the auditor's opinion from audit documents.

{metadata_str}

Context from Audit Documents:
{context}

Question: {query}

Instructions:
1. Identify the type of opinion (unqualified, qualified, adverse, disclaimer)
2. Extract the exact opinion statement from the context
3. Note any qualifications or modifications to the opinion
4. Include the basis for the opinion if mentioned
5. If opinion is not found, state: "The auditor's opinion is not available in the provided documents."
6. Be precise and quote directly from the context when possible

Answer:"""
    
    def _findings_prompt(self, query: str, context: str, role: Optional[str], metadata: Optional[Dict]) -> str:
        """Prompt for audit findings queries"""
        metadata_str = self._format_metadata(metadata)
        role_context = self._get_role_context(role)
        
        return f"""You are an audit findings analysis assistant. Extract and summarize audit findings from the provided context.

{metadata_str}
{role_context}

Context from Audit Documents:
{context}

Question: {query}

Instructions:
1. Identify all findings, deficiencies, or issues mentioned in the context
2. Categorize findings by severity (material weakness, significant deficiency, etc.)
3. For each finding, include:
   - Description of the finding
   - Affected area/process
   - Severity level
   - Any recommendations provided
4. If no findings are mentioned, state: "No audit findings are reported in the provided documents."
5. Be specific and cite the document/section for each finding

Answer:"""
    
    def _compliance_prompt(self, query: str, context: str, metadata: Optional[Dict]) -> str:
        """Prompt for compliance queries"""
        metadata_str = self._format_metadata(metadata)
        
        return f"""You are a compliance analysis assistant. Extract compliance-related information from audit documents.

{metadata_str}

Context from Audit Documents:
{context}

Question: {query}

Instructions:
1. Identify the compliance standard or regulation mentioned (GAAP, IFRS, SOX, HIPAA, etc.)
2. Extract compliance status (compliant, non-compliant, partially compliant)
3. Note any compliance issues or exceptions
4. Include relevant compliance testing procedures or assessments
5. If compliance information is not found, state: "Compliance information for the requested standard is not available in the provided documents."
6. Be specific about which standards are addressed

Answer:"""
    
    def _summary_prompt(self, query: str, context: str, role: Optional[str], metadata: Optional[Dict]) -> str:
        """Prompt for summary/overview queries"""
        metadata_str = self._format_metadata(metadata)
        role_context = self._get_role_context(role)
        
        return f"""You are an executive summary assistant. Provide a concise, structured summary based on the audit documents.

{metadata_str}
{role_context}

Context from Audit Documents:
{context}

Question: {query}

Instructions:
1. Provide a clear, structured summary covering:
   - Key findings or conclusions
   - Financial highlights (if applicable)
   - Major issues or concerns
   - Overall assessment
2. Organize information logically with clear sections
3. Focus on high-level insights relevant to {role or 'executives'}
4. Keep summary concise but comprehensive
5. Use bullet points or numbered lists for clarity
6. Cite document sources for key points

Answer:"""
    
    def _kam_prompt(self, query: str, context: str, metadata: Optional[Dict]) -> str:
        """Prompt for Key Audit Matters queries"""
        metadata_str = self._format_metadata(metadata)
        
        return f"""You are an audit analysis assistant. Extract Key Audit Matters (KAMs) from the audit documents.

{metadata_str}

Context from Audit Documents:
{context}

Question: {query}

Instructions:
1. Identify all Key Audit Matters mentioned in the context
2. For each KAM, extract:
   - Description of the matter
   - Why it was considered significant
   - How it was addressed in the audit
   - Reference to relevant financial statement areas
3. List KAMs in order of significance if multiple are mentioned
4. If no KAMs are found, state: "No Key Audit Matters are identified in the provided documents."
5. Be specific and cite document sections

Answer:"""
    
    def _comparison_prompt(self, query: str, context: str, metadata: Optional[Dict]) -> str:
        """Prompt for comparison queries"""
        metadata_str = self._format_metadata(metadata)
        
        return f"""You are a comparative analysis assistant. Compare information across audit documents or time periods.

{metadata_str}

Context from Audit Documents:
{context}

Question: {query}

Instructions:
1. Identify what is being compared (periods, documents, metrics)
2. Extract values or information for each item being compared
3. Calculate differences, changes, or trends
4. Present comparison in a clear format (table or structured list)
5. Include percentage changes if applicable
6. Note the time periods or documents being compared
7. If comparison cannot be made, state: "Insufficient information available for the requested comparison."

Answer:"""
    
    def _risk_prompt(self, query: str, context: str, metadata: Optional[Dict]) -> str:
        """Prompt for risk assessment queries"""
        metadata_str = self._format_metadata(metadata)
        
        return f"""You are a risk analysis assistant. Extract risk-related information from audit documents.

{metadata_str}

Context from Audit Documents:
{context}

Question: {query}

Instructions:
1. Identify all risk factors, uncertainties, or risk assessments mentioned
2. Categorize risks by type (financial, operational, compliance, market, etc.)
3. Note the severity or materiality of each risk
4. Include any risk mitigation strategies mentioned
5. Note any going concern considerations
6. If no risk information is found, state: "Risk information is not available in the provided documents."
7. Be specific about risk types and their implications

Answer:"""
    
    def _recommendations_prompt(self, query: str, context: str, metadata: Optional[Dict]) -> str:
        """Prompt for recommendations queries"""
        metadata_str = self._format_metadata(metadata)
        
        return f"""You are an audit recommendations assistant. Extract recommendations and action items from audit documents.

{metadata_str}

Context from Audit Documents:
{context}

Question: {query}

Instructions:
1. Identify all recommendations, suggestions, or action items mentioned
2. For each recommendation, include:
   - Description of the recommendation
   - Related finding or issue (if applicable)
   - Priority or urgency (if mentioned)
   - Responsible party or department (if mentioned)
3. Organize recommendations by category or priority
4. If no recommendations are found, state: "No recommendations are provided in the audit documents."
5. Be specific and actionable

Answer:"""
    
    def _metadata_prompt(self, query: str, context: str, metadata: Optional[Dict]) -> str:
        """Prompt for document metadata queries"""
        if metadata:
            doc_info = f"""
Available Documents:
{self._format_document_list(metadata)}
"""
        else:
            doc_info = ""
        
        return f"""You are answering a question about document metadata (titles, dates, auditors, etc.).

{doc_info}

Context:
{context}

Question: {query}

Instructions:
- Answer ONLY using the document information provided above
- If asking for titles, provide the actual document filenames
- If asking for dates, provide the audit period or report date
- If asking for auditor, provide the auditor firm name
- Be direct and concise
- If information is not available, state: "The requested information is not available."

Answer:"""
    
    def _general_prompt(self, query: str, context: str, role: Optional[str], metadata: Optional[Dict]) -> str:
        """General purpose prompt"""
        metadata_str = self._format_metadata(metadata)
        role_context = self._get_role_context(role)
        
        return f"""You are a professional audit document analysis assistant. Answer the question using ONLY the provided context from audit documents.

{metadata_str}
{role_context}

Context from Audit Documents:
{context}

Question: {query}

Instructions:
1. Read the question carefully to understand what is being asked
2. Search the context for information that directly answers the question
3. Base your answer STRICTLY on the provided context
4. If the answer is found, provide it clearly and concisely
5. Cite the document or section when referencing specific information
6. If the information is not available in the context, state: "Based on the provided documents, I cannot find sufficient information to answer this question."
7. Do NOT include random text that doesn't answer the question
8. Be accurate and professional

Answer:"""
    
    def _format_metadata(self, metadata: Optional[Dict]) -> str:
        """Format document metadata for prompt"""
        if not metadata:
            return ""
        
        parts = []
        if metadata.get('audit_period'):
            parts.append(f"Audit Period: {metadata['audit_period']}")
        if metadata.get('auditor'):
            parts.append(f"Auditor: {metadata['auditor']}")
        if metadata.get('auditee'):
            parts.append(f"Auditee: {metadata['auditee']}")
        if metadata.get('opinion_type'):
            parts.append(f"Opinion Type: {metadata['opinion_type']}")
        if metadata.get('document_type'):
            parts.append(f"Document Type: {metadata['document_type']}")
        
        if parts:
            return "Document Information:\n" + "\n".join(f"- {p}" for p in parts) + "\n"
        return ""
    
    def _format_document_list(self, metadata: Dict) -> str:
        """Format document list for metadata queries"""
        # This would be populated from actual document metadata
        return "Document information available in context"
    
    def _get_role_context(self, role: Optional[str]) -> str:
        """Get role-specific context for prompt"""
        if not role:
            return ""
        
        role_contexts = {
            'admin': "You are providing information to an administrator who manages the audit system.",
            'auditor': "You are providing information to an auditor who needs detailed technical information.",
            'viewer': "You are providing information to a viewer who needs clear, concise summaries.",
        }
        
        context = role_contexts.get(role.lower(), "")
        return context + "\n" if context else ""
