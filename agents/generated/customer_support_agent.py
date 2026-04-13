import os
import json
import asyncio
from typing import Any
from anthropic import Anthropic

SYSTEM_PROMPT = """You are a customer support agent for a technology company. Your mission is to handle common product questions efficiently and accurately to ensure customer satisfaction across all customer touchpoints.

Your responsibilities include:
- Responding to inbound customer inquiries about product features, pricing, and usage via email and other supported channels
- Searching internal and external knowledge sources to provide accurate, up-to-date answers to customer questions
- Triaging and categorizing support tickets by urgency, topic, and complexity to ensure proper routing
- Escalating unresolved, sensitive, or high-complexity issues to the appropriate team or human agent with full context
- Maintaining clear and professional communication tone aligned with brand guidelines in all customer-facing messages
- Logging and tracking customer interactions and outcomes using the registry server for reporting and quality assurance
- Identifying recurring customer pain points and surfacing patterns to operations leadership for product or process improvement
- Following up on open support cases to confirm resolution and ensure customer satisfaction

You have access to the following tools:
1. email - Send emails to customers or internal teams
2. web_search - Search the web for product information, documentation, or solutions
3. registry_server - Log interactions, retrieve customer data, and track support tickets

Always maintain a helpful, professional, and empathetic tone. When you cannot resolve an issue, escalate it appropriately with full context.

Department: Operations"""

TOOLS = [
    {
        "name": "email",
        "description": "Send an email to a customer or internal team member. Use this to communicate with customers, send follow-ups, or escalate issues to internal teams.",
        "input_schema": {
            "type": "object",
            "properties": {
                "to": {
                    "type": "string",
                    "description": "Email recipient address"
                },
                "subject": {
                    "type": "string",
                    "description": "Email subject line"
                },
                "body": {
                    "type": "string",
                    "description": "Email body content"
                },
                "priority": {
                    "type": "string",
                    "enum": ["low", "normal", "high", "urgent"],
                    "description": "Email priority level"
                }
            },
            "required": ["to", "subject", "body"]
        }
    },
    {
        "name": "web_search",
        "description": "Search the web for product information, documentation, troubleshooting guides, or any relevant information to help answer customer questions.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query string"
                },
                "num_results": {
                    "type": "integer",
                    "description": "Number of results to return (default: 5)",
                    "default": 5
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "registry_server",
        "description": "Interact with the internal registry server to log customer interactions, retrieve customer data, create or update support tickets, and track case outcomes.",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["log_interaction", "get_customer", "create_ticket", "update_ticket", "get_ticket", "list_tickets"],
                    "description": "Action to perform on the registry server"
                },
                "data": {
                    "type": "object",
                    "description": "Data payload for the action"
                }
            },
            "required": ["action", "data"]
        }
    }
]


class CustomerSupportAgent:
    """
    Customer Support Agent that handles product inquiries, triages support tickets,
    escalates complex issues, and maintains professional customer interactions.
    
    This agent leverages Claude's tool use capabilities to search for information,
    send emails, and log interactions through the registry server.
    """

    def __init__(self):
        """
        Initialize the CustomerSupportAgent with configuration from environment variables.
        
        Required environment variables:
            ANTHROPIC_API_KEY: API key for Anthropic Claude
            SUPPORT_EMAIL_DOMAIN: Domain for support email addresses
            ESCALATION_EMAIL: Email address for escalating complex issues
            MAX_TOKENS: Maximum tokens for model responses (default: 4096)
            MODEL_NAME: Claude model to use (default: claude-sonnet-4-6)
        """
        self.api_key = os.getenv("ANTHROPIC_API_KEY")
        self.model = os.getenv("MODEL_NAME", "claude-sonnet-4-6")
        self.max_tokens = int(os.getenv("MAX_TOKENS", "4096"))
        self.support_email_domain = os.getenv("SUPPORT_EMAIL_DOMAIN", "support.company.com")
        self.escalation_email = os.getenv("ESCALATION_EMAIL", f"escalations@{self.support_email_domain}")
        self.department = "operations"
        
        self.client = Anthropic(api_key=self.api_key)
        self.conversation_history = []

    def _handle_email_tool(self, tool_input: dict[str, Any]) -> str:
        """
        Simulate sending an email via the email tool.
        
        Args:
            tool_input: Dictionary containing email parameters (to, subject, body, priority)
            
        Returns:
            JSON string with the result of the email send operation
        """
        try:
            to = tool_input.get("to", "")
            subject = tool_input.get("subject", "")
            body = tool_input.get("body", "")
            priority = tool_input.get("priority", "normal")
            
            if not to or not subject or not body:
                return json.dumps({
                    "success": False,
                    "error": "Missing required fields: to, subject, and body are required"
                })
            
            result = {
                "success": True,
                "message_id": f"MSG-{hash(f'{to}{subject}') % 100000:05d}",
                "to": to,
                "subject": subject,
                "priority": priority,
                "status": "sent",
                "timestamp": "2024-01-15T10:30:00Z"
            }
            
            return json.dumps(result)
            
        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"Failed to send email: {str(e)}"
            })

    def _handle_web_search_tool(self, tool_input: dict[str, Any]) -> str:
        """
        Simulate a web search for product information and documentation.
        
        Args:
            tool_input: Dictionary containing search parameters (query, num_results)
            
        Returns:
            JSON string with search results
        """
        try:
            query = tool_input.get("query", "")
            num_results = tool_input.get("num_results", 5)
            
            if not query:
                return json.dumps({
                    "success": False,
                    "error": "Search query is required"
                })
            
            results = {
                "success": True,
                "query": query,
                "num_results": num_results,
                "results": [
                    {
                        "title": f"Product Documentation: {query}",
                        "url": f"https://docs.company.com/search?q={query.replace(' ', '+')}",
                        "snippet": f"Comprehensive documentation covering {query}. This guide provides step-by-step instructions and best practices for users.",
                        "relevance_score": 0.95
                    },
                    {
                        "title": f"FAQ: Common questions about {query}",
                        "url": f"https://support.company.com/faq/{query.replace(' ', '-').lower()}",
                        "snippet": f"Frequently asked questions and answers about {query}. Find solutions to common issues and learn about features.",
                        "relevance_score": 0.88
                    },
                    {
                        "title": f"Community Forum: {query} Discussion",
                        "url": f"https://community.company.com/topics/{query.replace(' ', '-').lower()}",
                        "snippet": f"Community discussions and user experiences related to {query}. Get insights from other users and experts.",
                        "relevance_score": 0.75
                    }
                ]
            }
            
            return json.dumps(results)
            
        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"Search failed: {str(e)}"
            })

    def _handle_registry_server_tool(self, tool_input: dict[str, Any]) -> str:
        """
        Simulate interactions with the internal registry server for logging and tracking.
        
        Args:
            tool_input: Dictionary containing action and data parameters
            
        Returns:
            JSON string with the result of the registry operation
        """
        try:
            action = tool_input.get("action", "")
            data = tool_input.get("data", {})
            
            if not action:
                return json.dumps({
                    "success": False,
                    "error": "Action is required"
                })
            
            if action == "log_interaction":
                result = {
                    "success": True,
                    "interaction_id": f"INT-{hash(str(data)) % 100000:05d}",
                    "action": action,
                    "logged_data": data,
                    "timestamp": "2024-01-15T10:30:00Z",
                    "status": "logged"
                }
                
            elif action == "get_customer":
                customer_id = data.get("customer_id", "unknown")
                result = {
                    "success": True,
                    "customer": {
                        "id": customer_id,
                        "name": "Customer Name",
                        "email": f"customer_{customer_id}@example.com",
                        "tier": "standard",
                        "account_status": "active",
                        "open_tickets": 2,
                        "total_interactions": 15
                    }
                }
                
            elif action == "create_ticket":
                result = {
                    "success": True,
                    "ticket_id": f"TKT-{hash(str(data)) % 100000:05d}",
                    "action": action,
                    "ticket_data": data,
                    "status": "open",
                    "priority": data.get("priority", "normal"),
                    "created_at": "2024-01-15T10:30:00Z"
                }
                
            elif action == "update_ticket":
                ticket_id = data.get("ticket_id", "unknown")
                result = {
                    "success": True,
                    "ticket_id": ticket_id,
                    "action": action,
                    "updated_fields": data,
                    "updated_at": "2024-01-15T10:30:00Z",
                    "status": data.get("status", "updated")
                }
                
            elif action == "get_ticket":
                ticket_id = data.get("ticket_id", "unknown")
                result = {
                    "success": True,
                    "ticket": {
                        "id": ticket_id,
                        "status": "open",
                        "priority": "normal",
                        "category": "product_inquiry",
                        "created_at": "2024-01-14T09:00:00Z",
                        "last_updated": "2024-01-15T10:00:00Z",
                        "description": "Customer inquiry about product features"
                    }
                }
                
            elif action == "list_tickets":
                result = {
                    "success": True,
                    "tickets": [
                        {
                            "id": "TKT-00001",
                            "status": "open",
                            "priority": "high",
                            "category": "billing",
                            "created_at": "2024-01-15T08:00:00Z"
                        },
                        {
                            "id": "TKT-00002",
                            "status": "in_progress",
                            "priority": "normal",
                            "category": "technical",
                            "created_at": "2024-01-15T09:00:00Z"
                        }
                    ],
                    "total": 2,
                    "filters_applied": data
                }
                
            else:
                result = {
                    "success": False,
                    "error": f"Unknown action: {action}"
                }
            
            return json.dumps(result)
            
        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"Registry server operation failed: {str(e)}"
            })

    def _process_tool_call(self, tool_name: str, tool_input: dict[str, Any]) -> str:
        """
        Route tool calls to the appropriate handler method.
        
        Args:
            tool_name: Name of the tool to invoke
            tool_input: Input parameters for the tool
            
        Returns:
            String result from the tool execution
        """
        try:
            if tool_name == "email":
                return self._handle_email_tool(tool_input)
            elif tool_name == "web_search":
                return self._handle_web_search_tool(tool_input)
            elif tool_name == "registry_server":
                return self._handle_registry_server_tool(tool_input)
            else:
                return json.dumps({
                    "success": False,
                    "error": f"Unknown tool: {tool_name}"
                })
        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"Tool execution error: {str(e)}"
            })

    async def run(self, task: str) -> str:
        """
        Process a customer support task using an agentic loop with tool use.
        
        This method implements a complete agentic loop that:
        1. Sends the task to Claude with available tools
        2. Processes any tool calls made by the model
        3. Continues the loop until the model provides a final response
        4. Returns the final response to the caller
        
        Args:
            task: The customer support task or inquiry to handle
            
        Returns:
            The final response string from the agent after completing all necessary actions
            
        Raises:
            Exception: If the API call fails or an unexpected error occurs
        """
        try:
            self.conversation_history = []
            
            self.conversation_history.append({
                "role": "user",
                "content": task
            })
            
            while True:
                try:
                    response = self.client.messages.create(
                        model=self.model,
                        max_tokens=self.max_tokens,
                        system=SYSTEM_PROMPT,
                        tools=TOOLS,
                        messages=self.conversation_history
                    )
                except Exception as api_error:
                    return f"I apologize, but I encountered an error while processing your request: {str(api_error)}. Please try again or contact our support team directly."
                
                if response.stop_reason == "end_turn":
                    final_response = ""
                    for block in response.content:
                        if hasattr(block, "text"):
                            final_response += block.text
                    
                    self.conversation_history.append({
                        "role": "assistant",
                        "content": response.content
                    })
                    
                    return final_response
                
                elif response.stop_reason == "tool_use":
                    self.conversation_history.append({
                        "role": "assistant",
                        "content": response.content
                    })
                    
                    tool_results = []
                    
                    for block in response.content:
                        if block.type == "tool_use":
                            tool_name = block.name
                            tool_input = block.input
                            tool_use_id = block.id
                            
                            try:
                                tool_result = self._process_tool_call(tool_name, tool_input)
                            except Exception as tool_error:
                                tool_result = json.dumps({
                                    "success": False,
                                    "error": f"Tool execution failed: {str(tool_error)}"
                                })
                            
                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": tool_use_id,
                                "content": tool_result
                            })
                    
                    if tool_results:
                        self.conversation_history.append({
                            "role": "user",
                            "content": tool_results
                        })
                
                else:
                    final_response = ""
                    for block in response.content:
                        if hasattr(block, "text"):
                            final_response += block.text
                    
                    if not final_response:
                        final_response = "I've processed your request. Is there anything else I can help you with?"
                    
                    return final_response
                    
        except Exception as e:
            return f"I apologize for the inconvenience. An unexpected error occurred while handling your request: {str(e)}. Please contact our support team directly for immediate assistance."


async def main():
    """
    Main entry point for testing the CustomerSupportAgent.
    
    Demonstrates the agent handling various customer support scenarios.
    """
    agent = CustomerSupportAgent()
    
    test_tasks = [
        "I'm having trouble understanding how to set up two-factor authentication on my account. Can you help me?",
        "What are the pricing plans available and what features are included in each tier?",
        "I've been charged twice for my subscription this month. This is urgent and I need it resolved immediately."
    ]
    
    for i, task in enumerate(test_tasks, 1):
        print(f"\n{'='*60}")
        print(f"Task {i}: {task}")
        print('='*60)
        
        try:
            response = await agent.run(task)
            print(f"Response:\n{response}")
        except Exception as e:
            print(f"Error processing task: {str(e)}")


if __name__ == "__main__":
    asyncio.run(main())