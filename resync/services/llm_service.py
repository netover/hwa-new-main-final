"""
LLM Service using OpenAI for NVIDIA API Integration

This service provides a unified interface for interacting with the NVIDIA API
through the OpenAI library, which has been tested and confirmed to work.
"""

import asyncio
import logging
from typing import AsyncGenerator, Optional, Dict, Any
from resync.settings import settings
from resync.core.exceptions import IntegrationError

try:
    from openai import AsyncOpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

logger = logging.getLogger(__name__)

class LLMService:
    """Service for interacting with LLM APIs through OpenAI"""
    
    def __init__(self):
        """Initialize the LLM service with NVIDIA API configuration"""
        if not OPENAI_AVAILABLE:
            raise IntegrationError(
                message="openai package is required but not installed",
                details={"install_command": "pip install openai"}
            )
        
        try:
            self.model = settings.llm_model
            self.default_temperature = 0.6
            self.default_top_p = 0.95
            self.default_max_tokens = 1000
            self.default_frequency_penalty = 0
            self.default_presence_penalty = 0
            
            # Initialize OpenAI client with NVIDIA API
            api_key = settings.llm_api_key
            base_url = settings.llm_endpoint

            # Debug logging
            # Avoid logging full API keys to prevent accidental exposure. Only log a few
            # characters for troubleshooting and mask the rest. If the key is shorter
            # than 4 characters, it will be fully masked.
            if api_key:
                masked = api_key[:4] + "..." if len(api_key) > 4 else "***"
                logger.info("Using LLM API key: %s", masked)
            else:
                logger.info("No LLM API key configured")
            logger.info("LLM base URL: %s", base_url)

            self.client = AsyncOpenAI(
                api_key=api_key,
                base_url=base_url,
            )
            
            logger.info(f"LLM service initialized with model: {self.model}")
            
        except Exception as e:
            logger.error(f"Failed to initialize LLM service: {e}")
            raise IntegrationError(
                message="Failed to initialize LLM service",
                details={"error": str(e)}
            ) from e

    async def generate_response(
        self,
        messages: list,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        max_tokens: Optional[int] = None,
        frequency_penalty: Optional[float] = None,
        presence_penalty: Optional[float] = None,
        stream: bool = False
    ) -> str:
        """
        Generate a response from the LLM
        
        Args:
            messages: List of message dictionaries with 'role' and 'content'
            temperature: Sampling temperature (0.0 to 2.0)
            top_p: Nucleus sampling parameter (0.0 to 1.0)
            max_tokens: Maximum number of tokens to generate
            frequency_penalty: Frequency penalty (-2.0 to 2.0)
            presence_penalty: Presence penalty (-2.0 to 2.0)
            stream: Whether to stream the response
            
        Returns:
            Generated text response
        """
        try:
            # Use default values if not provided
            temperature = temperature or self.default_temperature
            top_p = top_p or self.default_top_p
            max_tokens = max_tokens or self.default_max_tokens
            frequency_penalty = frequency_penalty or self.default_frequency_penalty
            presence_penalty = presence_penalty or self.default_presence_penalty

            logger.info(f"Generating LLM response with model: {self.model}")
            
            if stream:
                # Return the first chunk of the streaming response
                async for chunk in self._generate_response_streaming(
                    messages, temperature, top_p, max_tokens,
                    frequency_penalty, presence_penalty
                ):
                    return chunk
            else:
                # Generate regular response
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=temperature,
                    top_p=top_p,
                    max_tokens=max_tokens,
                    frequency_penalty=frequency_penalty,
                    presence_penalty=presence_penalty,
                    stream=False
                )
                
                content = response.choices[0].message.content
                logger.info(f"Generated LLM response ({len(content)} characters)")
                return content
                
        except Exception as e:
            logger.error(f"Error generating LLM response: {e}")
            raise IntegrationError(
                message="Failed to generate LLM response",
                details={"error": str(e), "model": self.model}
            ) from e

    async def _generate_response_streaming(
        self,
        messages: list,
        temperature: float,
        top_p: float,
        max_tokens: int,
        frequency_penalty: float,
        presence_penalty: float
    ) -> AsyncGenerator[str, None]:
        """
        Generate a streaming response from the LLM
        
        Args:
            messages: List of message dictionaries
            temperature: Sampling temperature
            top_p: Nucleus sampling parameter
            max_tokens: Maximum number of tokens to generate
            frequency_penalty: Frequency penalty
            presence_penalty: Presence penalty
            
        Yields:
            Chunks of the generated response
        """
        try:
            logger.info(f"Generating streaming LLM response with model: {self.model}")
            
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                top_p=top_p,
                max_tokens=max_tokens,
                frequency_penalty=frequency_penalty,
                presence_penalty=presence_penalty,
                stream=True
            )
            
            async for chunk in response:
                if chunk.choices[0].delta.content is not None:
                    content = chunk.choices[0].delta.content
                    yield content
                    
        except Exception as e:
            logger.error(f"Error generating streaming LLM response: {e}")
            raise IntegrationError(
                message="Failed to generate streaming LLM response",
                details={"error": str(e), "model": self.model}
            ) from e

    async def generate_system_status_message(
        self,
        system_info: Dict[str, Any]
    ) -> str:
        """
        Generate a status message about the system
        
        Args:
            system_info: Dictionary containing system information
            
        Returns:
            Generated status message
        """
        messages = [
            {
                "role": "system",
                "content": "Você é um assistente de IA do sistema Resync TWS Integration. "
                           "Forneça informações claras e concisas sobre o status do sistema "
                           "em português brasileiro. Seja profissional e útil."
            },
            {
                "role": "user",
                "content": f"Por favor, forneça um resumo do status atual do sistema: "
                           f"Com base nestas informações: {system_info}"
            }
        ]
        
        return await self.generate_response(messages, max_tokens=500)

    async def generate_agent_response(
        self,
        agent_id: str,
        user_message: str,
        conversation_history: Optional[list] = None,
        agent_config: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Generate a response from an AI agent
        
        Args:
            agent_id: ID of the agent
            user_message: User's message
            conversation_history: Previous conversation history
            agent_config: Agent configuration
            
        Returns:
            Generated agent response
        """
        # Build system message based on agent configuration
        agent_type = agent_config.get('type', 'general') if agent_config else 'general'
        agent_name = agent_config.get('name', f'Agente {agent_id}') if agent_config else f'Agente {agent_id}'
        agent_description = agent_config.get('description', f'Assistente {agent_type}') if agent_config else f'Assistente {agent_type}'
        
        system_message = (
            f"Você é {agent_name}, {agent_description}. "
            f"Responda de forma útil e profissional em português brasileiro. "
            f"Seja conciso e forneça informações precisas."
        )
        
        messages = [{"role": "system", "content": system_message}]
        
        # Add conversation history if available
        if conversation_history:
            messages.extend(conversation_history[-5:])  # Keep last 5 messages
        
        # Add current user message
        messages.append({"role": "user", "content": user_message})
        
        return await self.generate_response(messages, max_tokens=800)

    async def generate_rag_response(
        self,
        query: str,
        context: str,
        conversation_history: Optional[list] = None
    ) -> str:
        """
        Generate a response using RAG (Retrieval-Augmented Generation)
        
        Args:
            query: User's query
            context: Retrieved context/documents
            conversation_history: Previous conversation history
            
        Returns:
            Generated RAG response
        """
        system_message = (
            "Você é um assistente de IA especializado em responder perguntas "
            "baseado no contexto fornecido. Use as informações do contexto para "
            "responder de forma precisa e útil. Se o contexto não contiver "
            "informações suficientes, diga que não sabe. Responda em português brasileiro."
        )
        
        messages = [{"role": "system", "content": system_message}]
        
        # Add conversation history if available
        if conversation_history:
            messages.extend(conversation_history[-3:])  # Keep last 3 messages
        
        # Combine query and context
        contextual_query = (
            f"Contexto relevante:\n{context}\n\n"
            f"Pergunta do usuário: {query}"
        )
        
        messages.append({"role": "user", "content": contextual_query})
        
        return await self.generate_response(messages, max_tokens=1000)

    async def health_check(self) -> Dict[str, Any]:
        """
        Perform a health check on the LLM service
        
        Returns:
            Dictionary containing health status information
        """
        try:
            # Simple test message
            test_response = await self.generate_response(
                messages=[
                    {"role": "user", "content": "Responda apenas com 'OK'."}
                ],
                max_tokens=10
            )
            
            if "OK" in test_response:
                return {
                    "status": "healthy",
                    "model": self.model,
                    "endpoint": settings.llm_endpoint,
                    "test_response": test_response
                }
            else:
                return {
                    "status": "degraded",
                    "model": self.model,
                    "endpoint": settings.llm_endpoint,
                    "test_response": test_response,
                    "error": "Unexpected response"
                }
                
        except Exception as e:
            return {
                "status": "unhealthy",
                "model": self.model,
                "endpoint": settings.llm_endpoint,
                "error": str(e)
            }

    async def chat_completion(
        self,
        user_message: str,
        agent_id: str,
        agent_config: Optional[Dict[str, Any]] = None,
        conversation_history: Optional[list] = None,
        stream: bool = False
    ) -> str:
        """
        Simplified chat completion method
        
        Args:
            user_message: User's message
            agent_id: ID of the agent
            agent_config: Agent configuration
            conversation_history: Previous conversation history
            stream: Whether to stream the response
            
        Returns:
            Generated response
        """
        return await self.generate_agent_response(
            agent_id=agent_id,
            user_message=user_message,
            conversation_history=conversation_history,
            agent_config=agent_config
        )

# Global LLM service instance
llm_service = None

def get_llm_service() -> LLMService:
    """Get or create the global LLM service instance"""
    global llm_service
    if llm_service is None:
        llm_service = LLMService()
    return llm_service
