"""
Social Media Agent - Draft engaging, platform-optimized social media posts
and manage content strategy across multiple social media platforms.
"""

import asyncio
import json
import logging
import os
from typing import Any

import anthropic

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class SocialMediaAgent:
    """
    Social Media Agent for drafting platform-optimized content and managing
    social media strategy across Twitter/X, LinkedIn, Instagram, Facebook, and TikTok.
    
    This agent serves as the central content intelligence layer for the marketing
    department's social media presence, leveraging web search and filesystem tools
    to create engaging, data-driven content.
    """
    
    def __init__(self):
        """
        Initialize the Social Media Agent with configuration from environment variables.
        
        Required environment variables:
        - ANTHROPIC_API_KEY: API key for Anthropic Claude
        - MCP_FILESYSTEM_PATH: Path for filesystem MCP server (optional, defaults to current dir)
        - SOCIAL_MEDIA_BRAND_NAME: Brand name for consistent voice (optional)
        - SOCIAL_MEDIA_BRAND_VOICE: Brand voice description (optional)
        - SOCIAL_MEDIA_TARGET_AUDIENCE: Target audience description (optional)
        - SOCIAL_MEDIA_INDUSTRY: Industry/niche for content context (optional)
        """
        self.api_key = os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is required")
        
        self.model = os.getenv("SOCIAL_MEDIA_MODEL", "claude-sonnet-4-6")
        self.filesystem_path = os.getenv("MCP_FILESYSTEM_PATH", os.getcwd())
        self.brand_name = os.getenv("SOCIAL_MEDIA_BRAND_NAME", "Our Brand")
        self.brand_voice = os.getenv("SOCIAL_MEDIA_BRAND_VOICE", "professional yet approachable")
        self.target_audience = os.getenv("SOCIAL_MEDIA_TARGET_AUDIENCE", "general business audience")
        self.industry = os.getenv("SOCIAL_MEDIA_INDUSTRY", "technology")
        self.max_tokens = int(os.getenv("SOCIAL_MEDIA_MAX_TOKENS", "8096"))
        self.max_iterations = int(os.getenv("SOCIAL_MEDIA_MAX_ITERATIONS", "10"))
        
        # Initialize Anthropic client
        self.client = anthropic.Anthropic(api_key=self.api_key)
        
        # Define MCP server configurations
        self.mcp_servers = self._configure_mcp_servers()
        
        # System prompt for the agent
        self.system_prompt = self._build_system_prompt()
        
        logger.info(f"SocialMediaAgent initialized for brand: {self.brand_name}")
    
    def _configure_mcp_servers(self) -> list[dict[str, Any]]:
        """
        Configure MCP server connections for web search and filesystem access.
        
        Returns:
            List of MCP server configuration dictionaries.
        """
        servers = []
        
        # Filesystem MCP server
        filesystem_server = {
            "type": "stdio",
            "command": "npx",
            "args": [
                "-y",
                "@modelcontextprotocol/server-filesystem",
                self.filesystem_path
            ]
        }
        servers.append(filesystem_server)
        
        # Web search MCP server (Brave Search)
        brave_api_key = os.getenv("BRAVE_API_KEY")
        if brave_api_key:
            web_search_server = {
                "type": "stdio",
                "command": "npx",
                "args": [
                    "-y",
                    "@modelcontextprotocol/server-brave-search"
                ],
                "env": {
                    "BRAVE_API_KEY": brave_api_key
                }
            }
            servers.append(web_search_server)
        else:
            logger.warning("BRAVE_API_KEY not set - web search functionality will be limited")
        
        return servers
    
    def _build_system_prompt(self) -> str:
        """
        Build the comprehensive system prompt for the social media agent.
        
        Returns:
            Formatted system prompt string with brand context and platform guidelines.
        """
        return f"""You are an expert Social Media Content Strategist and Agent for {self.brand_name}.

MISSION:
Draft engaging, platform-optimized social media posts tailored to each channel's unique audience demographics, content formats, and algorithmic preferences. Suggest optimal posting schedules grounded in platform-specific engagement patterns and industry best practices to maximize visibility and interaction.

BRAND CONTEXT:
- Brand Name: {self.brand_name}
- Brand Voice: {self.brand_voice}
- Target Audience: {self.target_audience}
- Industry: {self.industry}

CORE RESPONSIBILITIES:
1. Draft platform-specific social media posts for Twitter/X, LinkedIn, Instagram, Facebook, and TikTok
2. Research trending topics, hashtags, and viral content patterns using web search
3. Suggest data-driven posting schedules based on platform best practices
4. Maintain consistent brand voice while allowing platform-appropriate stylistic variation
5. Generate content calendars with thematic campaigns and seasonal hooks
6. Recommend hashtag strategies, mention tactics, and engagement prompts
7. Review and adapt existing content assets from the filesystem
8. Analyze platform algorithm updates and content format trends

PLATFORM-SPECIFIC GUIDELINES:

Twitter/X:
- Character limit: 280 characters (threads for longer content)
- Tone: Conversational, witty, timely
- Optimal hashtags: 1-2 per tweet
- Best posting times: 8-10 AM, 12-1 PM, 5-6 PM (audience timezone)
- Content mix: 40% educational, 30% engaging/entertaining, 20% promotional, 10% personal

LinkedIn:
- Optimal length: 150-300 words for posts, longer for articles
- Tone: Professional, thought leadership, industry insights
- Hashtags: 3-5 relevant professional hashtags
- Best posting times: Tuesday-Thursday, 8-10 AM, 12 PM
- Content mix: 60% educational/insights, 25% company news, 15% promotional

Instagram:
- Caption length: 125-150 characters for feed, up to 2200 max
- Tone: Visual-first, aspirational, authentic
- Hashtags: 5-10 relevant hashtags (mix of popular and niche)
- Best posting times: 11 AM-1 PM, 7-9 PM
- Content mix: 40% lifestyle/brand, 30% product/service, 20% user-generated, 10% promotional

Facebook:
- Optimal length: 40-80 characters for highest engagement
- Tone: Community-focused, conversational, shareable
- Hashtags: 1-2 maximum
- Best posting times: 1-4 PM weekdays, 12-1 PM weekends
- Content mix: 50% entertaining/engaging, 30% educational, 20% promotional

TikTok:
- Caption length: 150-300 characters
- Tone: Authentic, trendy, entertaining, educational
- Hashtags: 3-5 trending + niche hashtags
- Best posting times: 7-9 AM, 12-3 PM, 7-11 PM
- Content mix: 60% entertaining/trending, 25% educational, 15% behind-the-scenes

CONTENT STRATEGY PRINCIPLES:
- Always include a clear call-to-action (CTA)
- Use engagement prompts (questions, polls, challenges)
- Incorporate trending topics when relevant to brand
- Maintain 80/20 rule: 80% value-adding content, 20% promotional
- Optimize for each platform's algorithm preferences
- Consider visual content recommendations alongside text

When using tools:
- Use web_search to research current trends, hashtags, and platform updates
- Use filesystem tools to read existing content assets and save content calendars
- Always provide complete, ready-to-post content (not templates)
- Include specific hashtags, emojis, and formatting for each platform

Provide actionable, specific recommendations with complete post drafts ready for immediate use."""
    
    async def run(self, task: str) -> str:
        """
        Execute a social media task using the agent with MCP tools.
        
        This method runs an agentic loop that processes the given task using
        Claude claude-sonnet-4-6 with access to web search and filesystem tools via MCP servers.
        The agent will iteratively use tools until the task is complete.
        
        Args:
            task: The social media task to execute (e.g., "Create a week of LinkedIn posts
                  about our new product launch", "Research trending hashtags for our industry",
                  "Generate a content calendar for next month")
        
        Returns:
            The agent's final response with completed social media content,
            strategy recommendations, or requested analysis.
        
        Raises:
            anthropic.APIError: If there's an API communication error
            ValueError: If the task is empty or invalid
        """
        if not task or not task.strip():
            raise ValueError("Task cannot be empty")
        
        logger.info(f"Starting social media task: {task[:100]}...")
        
        messages = [
            {
                "role": "user",
                "content": task
            }
        ]
        
        final_response = ""
        iteration_count = 0
        
        try:
            # Use MCP servers with the Anthropic client
            async with self.client.beta.messages.stream(
                model=self.model,
                max_tokens=self.max_tokens,
                system=self.system_prompt,
                messages=messages,
                mcp_servers=self.mcp_servers,
                betas=["mcp-client-2025-04-04"]
            ) as stream:
                # Collect the full response
                response = await stream.get_final_message()
                
                # Process the response
                final_response = self._extract_text_response(response)
                
                # Handle tool use in agentic loop
                while response.stop_reason == "tool_use" and iteration_count < self.max_iterations:
                    iteration_count += 1
                    logger.info(f"Agent iteration {iteration_count}: processing tool calls")
                    
                    # Add assistant response to messages
                    messages.append({
                        "role": "assistant",
                        "content": response.content
                    })
                    
                    # Process tool results
                    tool_results = self._process_tool_calls(response.content)
                    
                    if tool_results:
                        messages.append({
                            "role": "user",
                            "content": tool_results
                        })
                    
                    # Continue the conversation
                    async with self.client.beta.messages.stream(
                        model=self.model,
                        max_tokens=self.max_tokens,
                        system=self.system_prompt,
                        messages=messages,
                        mcp_servers=self.mcp_servers,
                        betas=["mcp-client-2025-04-04"]
                    ) as next_stream:
                        response = await next_stream.get_final_message()
                        final_response = self._extract_text_response(response)
                
                if iteration_count >= self.max_iterations:
                    logger.warning(f"Reached maximum iterations ({self.max_iterations})")
                
                logger.info(f"Task completed after {iteration_count} tool iterations")
                return final_response
                
        except anthropic.APIConnectionError as e:
            logger.error(f"API connection error: {e}")
            raise
        except anthropic.RateLimitError as e:
            logger.error(f"Rate limit exceeded: {e}")
            raise
        except anthropic.APIStatusError as e:
            logger.error(f"API status error {e.status_code}: {e.message}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during task execution: {e}")
            raise
    
    def _extract_text_response(self, response: anthropic.types.Message) -> str:
        """
        Extract text content from an Anthropic API response message.
        
        Args:
            response: The Anthropic API response message object.
        
        Returns:
            Concatenated text content from all text blocks in the response.
        """
        text_parts = []
        
        try:
            for block in response.content:
                if hasattr(block, 'type') and block.type == 'text':
                    text_parts.append(block.text)
        except Exception as e:
            logger.error(f"Error extracting text from response: {e}")
            return "Error processing response"
        
        return "\n".join(text_parts) if text_parts else ""
    
    def _process_tool_calls(self, content_blocks: list) -> list[dict[str, Any]]:
        """
        Process tool use blocks from the assistant's response.
        
        This method handles the tool call results that need to be fed back
        to the agent in the agentic loop. For MCP tools, the results are
        handled automatically by the MCP client.
        
        Args:
            content_blocks: List of content blocks from the assistant's response,
                          which may include tool_use blocks.
        
        Returns:
            List of tool result message content blocks for the next API call.
        """
        tool_results = []
        
        try:
            for block in content_blocks:
                if hasattr(block, 'type') and block.type == 'tool_use':
                    logger.info(f"Tool called: {block.name}")
                    # MCP tools handle their own execution
                    # We just need to acknowledge the tool use
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": "Tool execution handled by MCP server"
                    })
        except Exception as e:
            logger.error(f"Error processing tool calls: {e}")
        
        return tool_results
    
    def get_platform_guidelines(self, platform: str) -> dict[str, Any]:
        """
        Retrieve platform-specific content guidelines and best practices.
        
        Args:
            platform: Social media platform name (twitter, linkedin, instagram, 
                     facebook, tiktok)
        
        Returns:
            Dictionary containing platform-specific guidelines including character
            limits, optimal posting times, hashtag recommendations, and content mix.
        """
        guidelines = {
            "twitter": {
                "character_limit": 280,
                "thread_support": True,
                "optimal_hashtags": "1-2",
                "best_times": ["8-10 AM", "12-1 PM", "5-6 PM"],
                "best_days": ["Tuesday", "Wednesday", "Thursday"],
                "content_mix": {
                    "educational": "40%",
                    "engaging": "30%",
                    "promotional": "20%",
                    "personal": "10%"
                },
                "tone": "Conversational, witty, timely",
                "media_types": ["images", "GIFs", "videos", "polls"]
            },
            "linkedin": {
                "character_limit": 3000,
                "optimal_length": "150-300 words",
                "optimal_hashtags": "3-5",
                "best_times": ["8-10 AM", "12 PM"],
                "best_days": ["Tuesday", "Wednesday", "Thursday"],
                "content_mix": {
                    "educational": "60%",
                    "company_news": "25%",
                    "promotional": "15%"
                },
                "tone": "Professional, thought leadership",
                "media_types": ["images", "documents", "videos", "articles"]
            },
            "instagram": {
                "caption_limit": 2200,
                "optimal_caption": "125-150 characters",
                "optimal_hashtags": "5-10",
                "best_times": ["11 AM-1 PM", "7-9 PM"],
                "best_days": ["Monday", "Wednesday", "Friday"],
                "content_mix": {
                    "lifestyle": "40%",
                    "product": "30%",
                    "user_generated": "20%",
                    "promotional": "10%"
                },
                "tone": "Visual-first, aspirational, authentic",
                "media_types": ["photos", "reels", "stories", "carousels"]
            },
            "facebook": {
                "optimal_length": "40-80 characters",
                "optimal_hashtags": "1-2",
                "best_times": ["1-4 PM weekdays", "12-1 PM weekends"],
                "best_days": ["Wednesday", "Thursday", "Friday"],
                "content_mix": {
                    "entertaining": "50%",
                    "educational": "30%",
                    "promotional": "20%"
                },
                "tone": "Community-focused, conversational",
                "media_types": ["images", "videos", "links", "events"]
            },
            "tiktok": {
                "caption_limit": 2200,
                "optimal_caption": "150-300 characters",
                "optimal_hashtags": "3-5",
                "best_times": ["7-9 AM", "12-3 PM", "7-11 PM"],
                "best_days": ["Tuesday", "Thursday", "Friday"],
                "content_mix": {
                    "entertaining": "60%",
                    "educational": "25%",
                    "behind_scenes": "15%"
                },
                "tone": "Authentic, trendy, entertaining",
                "media_types": ["short_videos", "duets", "stitches"]
            }
        }
        
        platform_lower = platform.lower()
        if platform_lower in guidelines:
            return guidelines[platform_lower]
        else:
            logger.warning(f"Unknown platform: {platform}")
            return {}
    
    def create_content_brief(self, 
                            topic: str, 
                            platforms: list[str], 
                            campaign_type: str = "general") -> str:
        """
        Create a structured content brief for social media posts.
        
        Args:
            topic: The main topic or theme for the content.
            platforms: List of target social media platforms.
            campaign_type: Type of campaign (general, product_launch, event, 
                          seasonal, thought_leadership).
        
        Returns:
            Formatted content brief string ready to be used as a task for the agent.
        """
        platform_list = ", ".join(platforms)
        
        brief = f"""Create a comprehensive social media content package for the following:

TOPIC: {topic}
PLATFORMS: {platform_list}
CAMPAIGN TYPE: {campaign_type}
BRAND: {self.brand_name}
BRAND VOICE: {self.brand_voice}
TARGET AUDIENCE: {self.target_audience}
INDUSTRY: {self.industry}

Please provide:
1. Platform-specific post drafts for each of: {platform_list}
2. Recommended hashtags for each platform
3. Optimal posting schedule with specific times and days
4. Visual content recommendations (image/video concepts)
5. Engagement prompts and CTAs
6. Any trending topics or hashtags to incorporate (use web search)

Ensure all content:
- Maintains consistent brand voice while adapting to each platform's style
- Includes appropriate emojis and formatting
- Has clear calls-to-action
- Is ready to post immediately without further editing"""
        
        return brief


async def main():
    """
    Main entry point for testing the Social Media Agent.
    
    Demonstrates the agent's capabilities with sample tasks including
    content creation, trend research, and content calendar generation.
    """
    try:
        agent = SocialMediaAgent()
        
        # Example task: Create platform-specific posts
        task = """Research current trending topics in technology and create a complete 
        social media content package for announcing a new AI-powered productivity tool. 
        Include posts for Twitter/X, LinkedIn, and Instagram with appropriate hashtags, 
        optimal posting times, and engagement prompts. Also check if there are any 
        existing content assets in the filesystem that could be repurposed."""
        
        logger.info("Starting Social Media Agent...")
        result = await agent.run(task)
        
        print("\n" + "="*60)
        print("SOCIAL MEDIA AGENT RESPONSE:")
        print("="*60)
        print(result)
        print("="*60)
        
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        raise
    except Exception as e:
        logger.error(f"Agent execution failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())