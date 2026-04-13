import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Any

import anthropic

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ComplianceAgent:
    """
    Compliance Agent for reviewing documents and content against regulatory requirements.
    
    This agent systematically identifies policy violations, provides explanations of
    relevant rules, and recommends corrective actions to ensure organizational compliance.
    """
    
    def __init__(self):
        """
        Initialize the ComplianceAgent with configuration from environment variables.
        
        Reads all configuration from environment variables:
        - ANTHROPIC_API_KEY: API key for Anthropic Claude
        - COMPLIANCE_MODEL: Model to use (defaults to claude-sonnet-4-6)
        - COMPLIANCE_MAX_TOKENS: Maximum tokens for responses (defaults to 8096)
        - COMPLIANCE_DEPARTMENT: Department context (defaults to legal)
        - MCP_FILESYSTEM_PATH: Path for filesystem MCP server
        - MCP_REGISTRY_URL: URL for registry MCP server
        """
        self.api_key = os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is required")
        
        self.model = os.getenv("COMPLIANCE_MODEL", "claude-sonnet-4-6")
        self.max_tokens = int(os.getenv("COMPLIANCE_MAX_TOKENS", "8096"))
        self.department = os.getenv("COMPLIANCE_DEPARTMENT", "legal")
        self.mcp_filesystem_path = os.getenv("MCP_FILESYSTEM_PATH", "/tmp/compliance_docs")
        self.mcp_registry_url = os.getenv("MCP_REGISTRY_URL", "http://localhost:8080")
        
        self.client = anthropic.Anthropic(api_key=self.api_key)
        
        self.audit_trail = []
        
        self.system_prompt = """You are a compliance agent for the legal department. Your mission is to review documents and content against applicable regulatory requirements and internal policies to ensure organizational compliance.

Your responsibilities include:
1. Review submitted documents and content against applicable regulatory frameworks, industry standards, and internal policies to identify compliance gaps.
2. Flag potential policy violations with precise references to the specific rules, regulations, or policy clauses that are implicated.
3. Generate detailed compliance reports summarizing findings, risk levels, and the regulatory basis for each identified issue.
4. Recommend specific, actionable corrective measures to resolve violations and achieve full compliance with relevant requirements.
5. Search and retrieve current regulatory guidance, policy updates, and legal standards using approved tools to ensure assessments reflect up-to-date requirements.
6. Maintain a structured audit trail of reviewed documents, identified violations, and recommended remediation steps within each session.
7. Prioritize and categorize compliance issues by severity, distinguishing between critical violations, moderate risks, and minor procedural gaps.
8. Advise on policy interpretation when document language is ambiguous, providing reasoned analysis grounded in regulatory context.

When analyzing compliance issues:
- Always cite specific regulatory references (e.g., GDPR Article 6, SOX Section 302, HIPAA 45 CFR 164.312)
- Categorize violations as: CRITICAL (immediate legal risk), MODERATE (significant risk requiring prompt attention), or MINOR (procedural gaps)
- Provide actionable remediation steps with clear timelines
- Consider industry-specific regulations relevant to the content
- Use available tools to search for current regulatory guidance when needed

Format your compliance reports with:
- Executive Summary
- Detailed Findings (with severity levels)
- Regulatory References
- Remediation Recommendations
- Risk Assessment"""

    def _build_mcp_servers(self) -> list[dict[str, Any]]:
        """
        Build the MCP server configurations for available tools.
        
        Returns:
            List of MCP server configuration dictionaries for filesystem,
            registry, and web search capabilities.
        """
        servers = []
        
        filesystem_server = {
            "type": "stdio",
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-filesystem", self.mcp_filesystem_path],
            "env": {}
        }
        servers.append(filesystem_server)
        
        registry_server = {
            "type": "stdio", 
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-brave-search"],
            "env": {
                "BRAVE_API_KEY": os.getenv("BRAVE_API_KEY", "")
            }
        }
        servers.append(registry_server)
        
        return servers

    def _record_audit_entry(self, task: str, findings: str, timestamp: str) -> None:
        """
        Record an entry in the session audit trail.
        
        Args:
            task: The compliance task that was reviewed
            findings: Summary of compliance findings
            timestamp: ISO format timestamp of the review
        """
        audit_entry = {
            "timestamp": timestamp,
            "task_summary": task[:200] + "..." if len(task) > 200 else task,
            "findings_summary": findings[:500] + "..." if len(findings) > 500 else findings,
            "session_entry_id": len(self.audit_trail) + 1
        }
        self.audit_trail.append(audit_entry)
        logger.info(f"Audit entry recorded: Entry #{audit_entry['session_entry_id']}")

    def _format_audit_context(self) -> str:
        """
        Format the current session audit trail for inclusion in prompts.
        
        Returns:
            Formatted string representation of the audit trail,
            or empty string if no entries exist.
        """
        if not self.audit_trail:
            return ""
        
        audit_context = "\n\nSession Audit Trail:\n"
        for entry in self.audit_trail[-5:]:
            audit_context += f"- [{entry['timestamp']}] Entry #{entry['session_entry_id']}: {entry['task_summary']}\n"
        
        return audit_context

    async def run(self, task: str) -> str:
        """
        Execute a compliance review task using Claude with MCP tools.
        
        This method processes the compliance task through Claude claude-sonnet-4-6 with access
        to filesystem, registry, and web search tools via MCP servers. It maintains
        an audit trail of all reviewed documents and findings.
        
        Args:
            task: The compliance review task description, which may include
                  document content, policy questions, or regulatory inquiries.
        
        Returns:
            A comprehensive compliance report as a string, including findings,
            risk assessments, regulatory references, and remediation recommendations.
        
        Raises:
            Exception: Logs and re-raises any critical errors that prevent
                      completion of the compliance review.
        """
        timestamp = datetime.now().isoformat()
        logger.info(f"Starting compliance review at {timestamp}")
        
        audit_context = self._format_audit_context()
        
        enhanced_task = f"""Compliance Review Request - {timestamp}
Department: {self.department}
{audit_context}

Task: {task}

Please conduct a thorough compliance review of the above. Use available tools to:
1. Search for relevant regulatory requirements and recent updates
2. Access any referenced documents if file paths are provided
3. Cross-reference against known compliance frameworks

Provide a structured compliance report with executive summary, detailed findings with severity levels (CRITICAL/MODERATE/MINOR), specific regulatory citations, and actionable remediation steps."""

        mcp_servers = self._build_mcp_servers()
        
        try:
            response_text = await self._execute_with_mcp(enhanced_task, mcp_servers)
        except Exception as e:
            logger.error(f"MCP execution failed: {e}, falling back to direct API call")
            try:
                response_text = await self._execute_direct(enhanced_task)
            except Exception as fallback_error:
                logger.error(f"Direct API call also failed: {fallback_error}")
                raise fallback_error
        
        self._record_audit_entry(task, response_text, timestamp)
        
        return response_text

    async def _execute_with_mcp(self, task: str, mcp_servers: list[dict]) -> str:
        """
        Execute the compliance task using MCP servers for tool access.
        
        Args:
            task: The formatted compliance task with context
            mcp_servers: List of MCP server configurations
        
        Returns:
            The compliance report generated by Claude with tool access
        """
        server_configs = []
        for server in mcp_servers:
            try:
                if server["type"] == "stdio":
                    server_config = anthropic.types.beta.BetaRequestMCPServerStdioSchema(
                        type="stdio",
                        name=f"mcp_server_{len(server_configs)}",
                        command=server["command"],
                        args=server.get("args", []),
                        env=server.get("env", {})
                    )
                    server_configs.append(server_config)
            except Exception as e:
                logger.warning(f"Failed to configure MCP server: {e}")
        
        try:
            response = self.client.beta.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=self.system_prompt,
                messages=[
                    {"role": "user", "content": task}
                ],
                mcp_servers=server_configs,
                betas=["mcp-client-2025-04-04"]
            )
            
            response_text = ""
            for block in response.content:
                if hasattr(block, 'text'):
                    response_text += block.text
            
            return response_text if response_text else "Compliance review completed. No text response generated."
            
        except Exception as e:
            logger.error(f"MCP API call failed: {e}")
            raise

    async def _execute_direct(self, task: str) -> str:
        """
        Execute the compliance task directly without MCP tools as a fallback.
        
        Args:
            task: The formatted compliance task with context
        
        Returns:
            The compliance report generated by Claude without tool access
        """
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=self.system_prompt + "\n\nNote: External tools are currently unavailable. Provide compliance analysis based on your training knowledge.",
                messages=[
                    {"role": "user", "content": task}
                ]
            )
            
            response_text = ""
            for block in response.content:
                if hasattr(block, 'text'):
                    response_text += block.text
            
            return response_text if response_text else "Compliance review completed. No text response generated."
            
        except Exception as e:
            logger.error(f"Direct API call failed: {e}")
            raise

    def get_audit_trail(self) -> list[dict]:
        """
        Retrieve the complete audit trail for the current session.
        
        Returns:
            List of audit trail entries, each containing timestamp,
            task summary, findings summary, and entry ID.
        """
        return self.audit_trail.copy()

    def export_audit_trail(self) -> str:
        """
        Export the audit trail as a formatted JSON string.
        
        Returns:
            JSON-formatted string of the complete audit trail,
            suitable for logging or storage.
        """
        try:
            return json.dumps(self.audit_trail, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to export audit trail: {e}")
            return json.dumps({"error": str(e), "entries": len(self.audit_trail)})


async def main():
    """
    Main entry point for testing the ComplianceAgent.
    
    Demonstrates basic usage of the agent with a sample compliance review task.
    """
    try:
        agent = ComplianceAgent()
        
        test_task = """
        Review the following employee data handling policy for GDPR compliance:
        
        'Our company collects employee personal data including names, addresses, 
        salary information, and performance reviews. This data is stored in our 
        HR system and shared with third-party payroll processors. Employees can 
        request access to their data by emailing HR. Data is retained for 7 years 
        after employment ends. We may use employee data for marketing purposes 
        with their implied consent from their employment contract.'
        
        Please identify any GDPR compliance issues and provide remediation recommendations.
        """
        
        result = await agent.run(test_task)
        print("Compliance Review Result:")
        print("=" * 80)
        print(result)
        print("=" * 80)
        print(f"\nAudit Trail Entries: {len(agent.get_audit_trail())}")
        
    except Exception as e:
        logger.error(f"Agent execution failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())