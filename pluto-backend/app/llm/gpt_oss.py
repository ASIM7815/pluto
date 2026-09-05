"""GPT-OSS (Groq) API Client"""
import httpx
from typing import Optional, Dict, Any, List
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class GPTOSSClient:
    """Client for GPT-OSS API (Groq)"""
    
    def __init__(self):
        self.api_key = settings.gpt_oss_api_key
        self.base_url = settings.gpt_oss_base_url
        self.model = settings.gpt_oss_model
        self.client = httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            },
            timeout=60.0
        )
    
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> Dict[str, Any]:
        """
        Send chat completion request to GPT-OSS
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            tools: Optional list of available tools
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            
        Returns:
            API response dict
        """
        try:
            payload = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens
            }
            
            if tools:
                payload["tools"] = tools
                payload["tool_choice"] = "auto"
            
            logger.info("gpt_oss_request", model=self.model, message_count=len(messages))
            
            response = await self.client.post(
                f"{self.base_url}/chat/completions",
                json=payload
            )
            response.raise_for_status()
            
            result = response.json()
            logger.info("gpt_oss_response", finish_reason=result["choices"][0]["finish_reason"])
            
            return result
            
        except httpx.HTTPError as e:
            logger.error("gpt_oss_error", error=str(e))
            raise Exception(f"GPT-OSS API error: {str(e)}")
    
    async def extract_tool_call(self, response: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract tool call from GPT-OSS response"""
        try:
            choice = response["choices"][0]
            message = choice["message"]
            
            if "tool_calls" in message and message["tool_calls"]:
                tool_call = message["tool_calls"][0]
                
                # Parse arguments (they come as a JSON string)
                import json as js
                arguments_str = tool_call["function"]["arguments"]
                arguments = js.loads(arguments_str) if isinstance(arguments_str, str) else arguments_str
                
                result = {
                    "tool": tool_call["function"]["name"],
                    "arguments": arguments
                }
                
                logger.info("tool_call_extracted", tool=result["tool"], args=result["arguments"])
                return result
            
            return None
            
        except Exception as e:
            logger.error("tool_extraction_error", error=str(e), response=response)
            return None
    
    async def get_text_response(self, response: Dict[str, Any]) -> str:
        """Extract text content from GPT-OSS response"""
        try:
            return response["choices"][0]["message"]["content"]
        except Exception:
            return ""
    
    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()


# Singleton instance
gpt_oss_client = GPTOSSClient()
