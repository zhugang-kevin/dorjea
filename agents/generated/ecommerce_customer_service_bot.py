import os
import json
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from enum import Enum
import httpx
from pydantic import BaseModel, Field, validator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class InteractionType(Enum):
    """Types of customer interactions."""
    INQUIRY = "inquiry"
    ORDER_STATUS = "order_status"
    RETURN_INITIATION = "return_initiation"
    ACCOUNT_UPDATE = "account_update"
    PAYMENT_ISSUE = "payment_issue"
    TRACKING_ISSUE = "tracking_issue"
    WEBSITE_ERROR = "website_error"
    ESCALATION = "escalation"


class CustomerInteraction(BaseModel):
    """Model for tracking customer interactions."""
    interaction_id: str = Field(..., description="Unique identifier for the interaction")
    timestamp: datetime = Field(default_factory=datetime.now)
    customer_id: Optional[str] = Field(None, description="Customer identifier if provided")
    interaction_type: InteractionType
    query: str
    response: str
    actions_taken: List[str] = Field(default_factory=list)
    escalated: bool = False
    escalation_reason: Optional[str] = None
    issue_pattern_identified: bool = False
    pattern_description: Optional[str] = None
    
    @validator('customer_id')
    def validate_customer_id(cls, v):
        """Ensure customer ID doesn't contain unnecessary PII."""
        if v and len(v) > 50:
            raise ValueError("Customer ID appears to contain excessive information")
        return v


class EcommerceCustomerServiceBot:
    """
    E-commerce customer service bot for handling inquiries, processing orders,
    and resolving issues.
    """
    
    def __init__(self):
        """
        Initialize the bot with configuration from environment variables.
        """
        self.model_name = os.getenv("MODEL_NAME", "claude-sonnet-4-6")
        self.api_key = os.getenv("API_KEY")
        self.api_base_url = os.getenv("API_BASE_URL", "https://api.anthropic.com")
        self.filesystem_server_url = os.getenv("FILESYSTEM_SERVER_URL")
        self.web_search_url = os.getenv("WEB_SEARCH_URL")
        self.email_server_url = os.getenv("EMAIL_SERVER_URL")
        self.escalation_email = os.getenv("ESCALATION_EMAIL")
        self.operations_team_email = os.getenv("OPERATIONS_TEAM_EMAIL")
        self.log_directory = os.getenv("LOG_DIRECTORY", "./logs")
        
        if not self.api_key:
            raise ValueError("API_KEY environment variable is required")
        
        self.interactions: List[CustomerInteraction] = []
        self.http_client = httpx.AsyncClient(timeout=30.0)
        
        # Create log directory if it doesn't exist
        try:
            os.makedirs(self.log_directory, exist_ok=True)
        except Exception as e:
            logger.error(f"Failed to create log directory: {e}")
        
        logger.info("EcommerceCustomerServiceBot initialized successfully")
    
    async def _call_model(self, prompt: str) -> str:
        """
        Call the AI model with the given prompt.
        
        Args:
            prompt: The prompt to send to the model
            
        Returns:
            The model's response as a string
            
        Raises:
            httpx.HTTPError: If the API call fails
        """
        try:
            headers = {
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            }
            
            payload = {
                "model": self.model_name,
                "max_tokens": 1000,
                "messages": [{"role": "user", "content": prompt}]
            }
            
            response = await self.http_client.post(
                f"{self.api_base_url}/v1/messages",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            
            result = response.json()
            return result.get("content", [{}])[0].get("text", "")
            
        except httpx.HTTPError as e:
            logger.error(f"Model API call failed: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in model call: {e}")
            raise
    
    async def _use_filesystem_server(self, operation: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Interact with the filesystem server.
        
        Args:
            operation: The operation to perform
            data: The data for the operation
            
        Returns:
            The response from the filesystem server
        """
        if not self.filesystem_server_url:
            raise ValueError("Filesystem server URL not configured")
        
        try:
            response = await self.http_client.post(
                f"{self.filesystem_server_url}/{operation}",
                json=data
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Filesystem server operation failed: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in filesystem operation: {e}")
            raise
    
    async def _use_web_search(self, query: str) -> Dict[str, Any]:
        """
        Perform a web search.
        
        Args:
            query: The search query
            
        Returns:
            The search results
        """
        if not self.web_search_url:
            raise ValueError("Web search URL not configured")
        
        try:
            response = await self.http_client.post(
                self.web_search_url,
                json={"query": query}
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Web search failed: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in web search: {e}")
            raise
    
    async def _send_email(self, to: str, subject: str, body: str) -> bool:
        """
        Send an email.
        
        Args:
            to: Recipient email address
            subject: Email subject
            body: Email body
            
        Returns:
            True if email was sent successfully, False otherwise
        """
        if not self.email_server_url:
            raise ValueError("Email server URL not configured")
        
        try:
            response = await self.http_client.post(
                self.email_server_url,
                json={
                    "to": to,
                    "subject": subject,
                    "body": body
                }
            )
            response.raise_for_status()
            return True
        except httpx.HTTPError as e:
            logger.error(f"Email sending failed: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error in email sending: {e}")
            return False
    
    def _analyze_interaction_type(self, query: str) -> InteractionType:
        """
        Analyze the query to determine the interaction type.
        
        Args:
            query: The customer's query
            
        Returns:
            The determined interaction type
        """
        query_lower = query.lower()
        
        if any(term in query_lower for term in ["order status", "where is my order", "track my order"]):
            return InteractionType.ORDER_STATUS
        elif any(term in query_lower for term in ["return", "refund", "exchange"]):
            return InteractionType.RETURN_INITIATION
        elif any(term in query_lower for term in ["account", "update", "change", "password"]):
            return InteractionType.ACCOUNT_UPDATE
        elif any(term in query_lower for term in ["payment failed", "payment issue", "card declined"]):
            return InteractionType.PAYMENT_ISSUE
        elif any(term in query_lower for term in ["tracking", "shipping", "delivery"]):
            return InteractionType.TRACKING_ISSUE
        elif any(term in query_lower for term in ["website", "error", "bug", "not working"]):
            return InteractionType.WEBSITE_ERROR
        else:
            return InteractionType.INQUIRY
    
    def _check_for_escalation(self, query: str) -> tuple[bool, Optional[str]]:
        """
        Check if the query should be escalated to a human agent.
        
        Args:
            query: The customer's query
            
        Returns:
            Tuple of (should_escalate, reason)
        """
        query_lower = query.lower()
        
        # Check for sensitive topics
        sensitive_terms = [
            "legal", "lawsuit", "attorney", "lawyer",
            "data breach", "security breach",
            "ceo", "executive", "management",
            "regulatory", "compliance"
        ]
        
        for term in sensitive_terms:
            if term in query_lower:
                return True, f"Sensitive topic detected: {term}"
        
        # Check for policy exception requests
        policy_exception_terms = [
            "exception", "override", "special treatment",
            "make an exception", "bend the rules"
        ]
        
        for term in policy_exception_terms:
            if term in query_lower:
                return True, f"Policy exception requested: {term}"
        
        # Check for complex technical issues
        complex_terms = [
            "database", "server", "api", "integration",
            "system down", "outage", "critical error"
        ]
        
        for term in complex_terms:
            if term in query_lower:
                return True, f"Complex technical issue: {term}"
        
        return False, None
    
    def _check_for_issue_patterns(self, interaction: CustomerInteraction) -> bool:
        """
        Check if this interaction indicates a recurring issue pattern.
        
        Args:
            interaction: The customer interaction
            
        Returns:
            True if a pattern is identified, False otherwise
        """
        # Check recent interactions for similar issues
        recent_interactions = [
            i for i in self.interactions[-10:] 
            if i.interaction_type == interaction.interaction_type
            and i != interaction
        ]
        
        if len(recent_interactions) >= 3:
            interaction.issue_pattern_identified = True
            interaction.pattern_description = f"Multiple similar {interaction.interaction_type.value} issues reported recently"
            return True
        
        return False
    
    async def _process_order_status(self, query: str) -> str:
        """
        Process an order status inquiry.
        
        Args:
            query: The customer's query
            
        Returns:
            Response to the customer
        """
        try:
            # Extract order number from query
            prompt = f"""
            Extract the order number from this customer query: "{query}"
            Return only the order number if found, otherwise return "NOT_FOUND".
            """
            
            order_number = await self._call_model(prompt)
            
            if order_number.strip() == "NOT_FOUND":
                return "I need your order number to check the status. Please provide your order number."
            
            # Try to get order information from filesystem
            try:
                order_data = await self._use_filesystem_server(
                    "get_order",
                    {"order_number": order_number.strip()}
                )
                
                if order_data.get("status") == "found":
                    status = order_data.get("order_status", "unknown")
                    shipping_info = order_data.get("shipping_info", {})
                    
                    return f"Your order #{order_number.strip()} is currently {status}. " \
                           f"Shipping to: {shipping_info.get('address', 'address not available')}. " \
                           f"Estimated delivery: {shipping_info.get('estimated_delivery', 'not available')}."
                else:
                    return f"I couldn't find order #{order_number.strip()} in our system. " \
                           f"Please verify the order number or contact support if you believe this is an error."
                    
            except Exception as e:
                logger.error(f"Failed to retrieve order data: {e}")
                return f"I'm having trouble accessing the order information for #{order_number.strip()}. " \
                       f"Please try again in a few minutes or contact support if the issue persists."
                        
        except Exception as e:
            logger.error(f"Error processing order status: {e}")
            return "I encountered an error while processing your order status request. Please try again."
    
    async def _process_return_initiation(self, query: str) -> str:
        """
        Process a return initiation request.
        
        Args:
            query: The customer's query
            
        Returns:
            Response to the customer
        """
        try:
            prompt = f"""
            Based on this return request: "{query}"
            Provide a response that:
            1. Acknowledges the return request
            2. Asks for the order number and item details
            3. Explains our return policy (30-day window, items must be unused)
            4. Provides instructions for next steps
            
            Keep the response friendly and helpful.
            """
            
            return await self._call_model(prompt)
            
        except Exception as e:
            logger.error(f"Error processing return initiation: {e}")
            return "I encountered an error while processing your return request. Please try again or contact support."
    
    async def _process_account_update(self, query: str) -> str:
        """
        Process an account update request.
        
        Args:
            query: The customer's query
            
        Returns:
            Response to the customer
        """
        try:
            prompt = f"""
            Based on this account update request: "{query}"
            Provide a response that:
            1. Acknowledges the request