import os
import json
import asyncio
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import httpx
from pydantic import BaseModel, Field

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ContentRequest(BaseModel):
    """Pydantic model for content generation requests."""
    task: str = Field(..., description="The content creation task description")
    content_type: Optional[str] = Field(None, description="Type of content (blog, social, email, etc.)")
    target_platform: Optional[str] = Field(None, description="Target platform for the content")
    brand_guidelines: Optional[str] = Field(None, description="Brand guidelines to follow")
    tone: Optional[str] = Field(None, description="Desired tone of voice")
    word_count: Optional[int] = Field(None, description="Target word count")
    keywords: Optional[List[str]] = Field(None, description="Keywords to include")


class ContentCreationAssistant:
    """
    An AI agent for generating, editing, and organizing high-quality, brand-aligned content
    across multiple formats and platforms to support strategic marketing objectives.
    """
    
    def __init__(self):
        """
        Initialize the ContentCreationAssistant with configuration from environment variables.
        
        Environment Variables:
            ANTHROPIC_API_KEY: API key for Claude Sonnet 4-6
            ANTHROPIC_API_URL: API endpoint URL (defaults to Anthropic's API)
            FILESYSTEM_SERVER_URL: URL for filesystem server
            WEB_SEARCH_URL: URL for web search service
            DEFAULT_CONTENT_DIR: Default directory for content storage
            MAX_RESEARCH_RESULTS: Maximum number of research results to use
            DEFAULT_WORD_COUNT: Default word count for content generation
        """
        try:
            self.api_key = os.getenv("ANTHROPIC_API_KEY")
            if not self.api_key:
                raise ValueError("ANTHROPIC_API_KEY environment variable is required")
            
            self.api_url = os.getenv("ANTHROPIC_API_URL", "https://api.anthropic.com/v1/messages")
            self.filesystem_url = os.getenv("FILESYSTEM_SERVER_URL")
            self.web_search_url = os.getenv("WEB_SEARCH_URL")
            self.default_content_dir = os.getenv("DEFAULT_CONTENT_DIR", "./content")
            self.max_research_results = int(os.getenv("MAX_RESEARCH_RESULTS", "5"))
            self.default_word_count = int(os.getenv("DEFAULT_WORD_COUNT", "500"))
            
            self.model = "claude-3-5-sonnet-20241022"
            self.department = "marketing"
            
            self.responsibilities = [
                "Generate original written content for blogs, social media, websites, and emails.",
                "Edit and proofread content for clarity, grammar, style, and brand consistency.",
                "Organize and manage digital content assets within the designated file structure.",
                "Conduct research to support content creation and ensure accuracy.",
                "Adapt existing content for different platforms and formats.",
                "Adhere to and promote the use of defined content workflows and approval processes."
            ]
            
            self.allowed_tools = ['filesystem_server', 'web_search']
            
            logger.info(f"ContentCreationAssistant initialized for department: {self.department}")
            logger.info(f"Using model: {self.model}")
            
        except Exception as e:
            logger.error(f"Failed to initialize ContentCreationAssistant: {str(e)}")
            raise
    
    async def _call_claude_api(self, prompt: str, system_prompt: str = None) -> str:
        """
        Make an API call to Claude Sonnet 4-6 model.
        
        Args:
            prompt: The user prompt/message
            system_prompt: Optional system prompt for context
            
        Returns:
            The model's response as a string
            
        Raises:
            Exception: If the API call fails
        """
        try:
            headers = {
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            }
            
            messages = [{"role": "user", "content": prompt}]
            
            data = {
                "model": self.model,
                "messages": messages,
                "max_tokens": 4000
            }
            
            if system_prompt:
                data["system"] = system_prompt
            
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(self.api_url, headers=headers, json=data)
                response.raise_for_status()
                result = response.json()
                
                if "content" in result and len(result["content"]) > 0:
                    return result["content"][0]["text"]
                else:
                    raise ValueError("Invalid response format from Claude API")
                    
        except httpx.HTTPError as e:
            logger.error(f"HTTP error calling Claude API: {str(e)}")
            raise Exception(f"Failed to call Claude API: {str(e)}")
        except Exception as e:
            logger.error(f"Error calling Claude API: {str(e)}")
            raise
    
    async def _call_filesystem_server(self, action: str, path: str, data: Any = None) -> Dict[str, Any]:
        """
        Call the filesystem server for file operations.
        
        Args:
            action: The filesystem action (read, write, list, etc.)
            path: The file or directory path
            data: Optional data for write operations
            
        Returns:
            Response from filesystem server
            
        Raises:
            Exception: If filesystem server is not configured or call fails
        """
        if not self.filesystem_url:
            raise Exception("Filesystem server URL not configured")
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                payload = {"action": action, "path": path}
                if data is not None:
                    payload["data"] = data
                
                response = await client.post(self.filesystem_url, json=payload)
                response.raise_for_status()
                return response.json()
                
        except httpx.HTTPError as e:
            logger.error(f"HTTP error calling filesystem server: {str(e)}")
            raise Exception(f"Filesystem server error: {str(e)}")
        except Exception as e:
            logger.error(f"Error calling filesystem server: {str(e)}")
            raise
    
    async def _call_web_search(self, query: str) -> List[Dict[str, Any]]:
        """
        Perform web search for research purposes.
        
        Args:
            query: Search query string
            
        Returns:
            List of search results
            
        Raises:
            Exception: If web search service is not configured or call fails
        """
        if not self.web_search_url:
            raise Exception("Web search URL not configured")
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                payload = {"query": query, "max_results": self.max_research_results}
                response = await client.post(self.web_search_url, json=payload)
                response.raise_for_status()
                result = response.json()
                
                if isinstance(result, list):
                    return result
                elif isinstance(result, dict) and "results" in result:
                    return result["results"]
                else:
                    return []
                    
        except httpx.HTTPError as e:
            logger.error(f"HTTP error calling web search: {str(e)}")
            raise Exception(f"Web search error: {str(e)}")
        except Exception as e:
            logger.error(f"Error calling web search: {str(e)}")
            raise
    
    async def _parse_content_request(self, task: str) -> ContentRequest:
        """
        Parse and analyze the content creation task to extract requirements.
        
        Args:
            task: The content creation task description
            
        Returns:
            Structured ContentRequest object
        """
        try:
            system_prompt = """You are a content strategy analyzer. Analyze the given content creation task 
            and extract the following information:
            1. Content type (blog, social media, email, website, etc.)
            2. Target platform (if specified)
            3. Brand guidelines or tone hints
            4. Desired word count or length
            5. Keywords or topics to focus on
            
            Return a JSON object with these fields."""
            
            prompt = f"""Analyze this content creation task and extract the requirements:
            
            Task: {task}
            
            Return ONLY a JSON object with these fields:
            - content_type (string, optional)
            - target_platform (string, optional)
            - brand_guidelines (string, optional)
            - tone (string, optional)
            - word_count (integer, optional)
            - keywords (array of strings, optional)"""
            
            response = await self._call_claude_api(prompt, system_prompt)
            
            # Extract JSON from response
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                data = json.loads(json_str)
                return ContentRequest(task=task, **data)
            else:
                return ContentRequest(task=task)
                
        except Exception as e:
            logger.warning(f"Failed to parse content request, using defaults: {str(e)}")
            return ContentRequest(task=task)
    
    async def _conduct_research(self, content_request: ContentRequest) -> str:
        """
        Conduct research for content creation using web search.
        
        Args:
            content_request: The parsed content request
            
        Returns:
            Research summary as a string
        """
        try:
            # Build search queries from task and keywords
            queries = []
            
            # Use the main task as a query
            queries.append(content_request.task)
            
            # Add keyword-based queries
            if content_request.keywords:
                for keyword in content_request.keywords[:3]:  # Limit to 3 keywords
                    queries.append(f"{keyword} {content_request.content_type or 'content'}")
            
            # Add platform-specific queries
            if content_request.target_platform:
                queries.append(f"{content_request.target_platform} best practices")
            
            all_results = []
            for query in queries[:2]:  # Limit to 2 queries to avoid too many requests
                try:
                    results = await self._call_web_search(query)
                    all_results.extend(results)
                except Exception as e:
                    logger.warning(f"Web search failed for query '{query}': {str(e)}")
            
            if not all_results:
                return "No research results found."
            
            # Summarize research results
            research_summary = "Research Findings:\n\n"
            for i, result in enumerate(all_results[:self.max_research_results], 1):
                title = result.get('title', 'No title')
                snippet = result.get('snippet', 'No description')
                url = result.get('url', 'No URL')
                
                research_summary += f"{i}. {title}\n"
                research_summary += f"   {snippet}\n"
                research_summary += f"   Source: {url}\n\n"
            
            return research_summary
            
        except Exception as e:
            logger.error(f"Research failed: {str(e)}")
            return f"Research could not be completed: {str(e)}"
    
    async def _generate_content(self, content_request: ContentRequest, research: str = "") -> str:
        """
        Generate content using Claude based on the request and research.
        
        Args:
            content_request: The parsed content request
            research: Optional research findings
            
        Returns:
            Generated content as a string
        """
        try:
            system_prompt = f"""You are a professional content creator for the {self.department} department.
            
            Your responsibilities:
            {chr(10).join(f'- {r}' for r in self.responsibilities)}
            
            Always create high-quality, brand-aligned content that supports strategic marketing objectives.
            Ensure content is clear, grammatically correct, and engaging."""
            
            prompt = f"""Create {content_request.content_type or 'content'} for {content_request.target_platform or 'multiple platforms'}.
            
            Task: {content_request.task}
            
            Requirements:
            - Tone: {content_request.tone or 'professional and engaging'}
            - Target length: {content_request.word_count or self.default_word_count} words
            {f'- Keywords to include: {", ".join(content_request.keywords)}' if content_request.keywords else ''}
            {f'- Brand guidelines: {content_request.brand_guidelines}' if content_request.brand_guidelines else ''}
            
            {f'Research Context:\n{research}' if research else 'No research provided.'}
            
            Please provide the complete content, ready for use. Include any necessary formatting."""
            
            content = await self._call_claude_api(prompt, system_prompt)
            return content
            
        except Exception as e:
            logger.error(f"Content generation failed: {str(e)}")
            raise Exception(f"Failed to generate content: {str(e)}")
    
    async def _edit_and_proofread(self, content: str, content_request: ContentRequest) -> str:
        """
        Edit and proofread generated content.
        
        Args:
            content: The content to edit
            content_request: The original content request for context
            
        Returns:
            Edited and proofread content
        """
        try:
            system_prompt = """You are a professional editor and proofreader. Your task is to:
            1. Check for grammar, spelling, and punctuation errors
            2. Improve clarity and readability
            3. Ensure brand consistency
            4. Optimize for the target platform
            5. Verify accuracy