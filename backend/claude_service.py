#!/usr/bin/env python3
"""
Claude AI Service for Teler Call Service
Provides AI-powered call flow generation and conversation handling.
"""

import os
import logging
from typing import Dict, Any, Optional
try:
    from anthropic import Anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    Anthropic = None
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

class ClaudeService:
    """Service for interacting with Anthropic Claude API."""
    
    def __init__(self):
        self.api_key = os.getenv('ANTHROPIC_API_KEY')
        self.client = None
        
        logger.info(f"ANTHROPIC_API_KEY found: {bool(self.api_key)}")
        logger.info(f"Anthropic library available: {ANTHROPIC_AVAILABLE}")
        
        if not ANTHROPIC_AVAILABLE:
            logger.warning("Anthropic library not available, Claude features will be disabled")
            return
            
        if not self.api_key:
            logger.warning("ANTHROPIC_API_KEY not found, Claude features will be disabled")
            return
        
        try:
            # Initialize with minimal parameters to avoid any version conflicts
            self.client = Anthropic(api_key=self.api_key)
            logger.info("Claude service initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Claude service: {str(e)}")
            self.client = None
    
    def is_available(self) -> bool:
        """Check if Claude service is available."""
        return self.client is not None
    
    async def generate_call_flow(self, call_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate a dynamic call flow based on call context using Claude.
        
        Args:
            call_context: Dictionary containing call information
            
        Returns:
            Dictionary containing the generated call flow
        """
        if not self.is_available():
            return self._get_conversation_flow()
        
        try:
            prompt = self._build_flow_generation_prompt(call_context)
            
            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1000,
                temperature=0.3,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )
            
            # Parse Claude's response to extract call flow
            flow_config = self._parse_flow_response(response.content[0].text)
            logger.info(f"Generated call flow using Claude: {flow_config}")
            
            return flow_config
            
        except Exception as e:
            logger.error(f"Error generating call flow with Claude: {str(e)}")
            return self._get_conversation_flow()
    
    async def generate_conversation_response(self, conversation_context: Dict[str, Any]) -> str:
        """
        Generate a conversation response using Claude.

        Args:
            conversation_context: Dictionary containing conversation history and context

        Returns:
            Generated response text
        """
        if not self.is_available():
            return "Hello! How can I help you today?"

        try:
            from rag_service import rag_service

            knowledge_base_context = ""
            knowledge_base_id = conversation_context.get('knowledge_base_id')
            current_input = conversation_context.get('current_input', '')

            logger.info(f"🔍 KB Lookup - ID: {knowledge_base_id}, Query: '{current_input}', RAG Available: {rag_service.is_available()}")

            if knowledge_base_id and current_input and rag_service.is_available():
                logger.info(f"📚 Querying knowledge base: {knowledge_base_id} with query: '{current_input}'")
                knowledge_base_context = await rag_service.get_context_for_query(
                    query=current_input,
                    knowledge_base_id=knowledge_base_id,
                    max_tokens=2000
                )
                logger.info(f"✓ Retrieved context length: {len(knowledge_base_context)} chars")
                if knowledge_base_context:
                    logger.info(f"📝 Context preview: {knowledge_base_context[:200]}...")
                else:
                    logger.warning("⚠️ Knowledge base returned empty context")
            else:
                logger.warning(f"⚠️ Skipping KB query - ID: {knowledge_base_id}, Query: {bool(current_input)}, RAG: {rag_service.is_available()}")

            prompt = self._build_conversation_prompt(conversation_context, knowledge_base_context)

            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=500,
                temperature=0.7,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )

            return response.content[0].text.strip()

        except Exception as e:
            logger.error(f"Error generating conversation response with Claude: {str(e)}")
            return "I apologize, but I'm having trouble processing your request right now."
    
    def _build_flow_generation_prompt(self, call_context: Dict[str, Any]) -> str:
        """Build prompt for call flow generation."""
        return f"""
        Generate a call flow configuration for a CONVERSATIONAL voice call with the following context:
        
        From: {call_context.get('from_number', 'Unknown')}
        To: {call_context.get('to_number', 'Unknown')}
        Purpose: {call_context.get('purpose', 'General call')}
        
        IMPORTANT: This call flow must enable REAL PHONE CONVERSATION between two people.
        The call should NOT end automatically after answering. It should:
        
        1. Answer the call automatically
        2. Play a brief greeting (max 5 seconds)
        3. Enable bidirectional conversation mode
        4. Keep the call active for actual human-to-human conversation
        5. Only end when explicitly requested or after long silence
        
        Please provide a JSON configuration that includes:
        1. Call answering and greeting
        2. Continuous conversation mode (not just listen/respond cycles)
        3. Proper call termination handling
        4. Recording and audio quality settings
        5. Silence detection and handling
        
        Format the response as a valid JSON object that can be used for call flow configuration.
        Focus on enabling REAL PHONE CONVERSATION, not automated responses.
        """
    
    def _build_conversation_prompt(self, conversation_context: Dict[str, Any], knowledge_base_context: str = "") -> str:
        """Build prompt for conversation response generation."""
        history = conversation_context.get('history', [])
        current_input = conversation_context.get('current_input', '')
        context = conversation_context.get('context', {})

        language = context.get('language', 'en-IN')
        language_name = self._get_language_name(language)

        history_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in history])

        kb_instructions = ""
        if knowledge_base_context:
            kb_instructions = f"""

        CRITICAL - KNOWLEDGE BASE CONTEXT:
        You MUST use the following information from the knowledge base to answer questions.
        This is the PRIMARY source of truth for all responses.

        --- KNOWLEDGE BASE START ---
        {knowledge_base_context}
        --- KNOWLEDGE BASE END ---

        MANDATORY RULES:
        1. ALWAYS prioritize information from the knowledge base above
        2. Answer questions ONLY using the knowledge base context provided
        3. If the exact answer is not in the context, say: "I don't have that specific information in my knowledge base."
        4. DO NOT use general knowledge or assumptions - ONLY use the knowledge base content
        5. Be direct and specific - cite relevant information from the knowledge base
        6. Keep responses SHORT (1-2 sentences) but accurate
        """

        return f"""
        You are an AI assistant in a voice call conversation in {language_name}.

        IMPORTANT CONVERSATION RULES:
        1. Keep responses SHORT (1-2 sentences maximum)
        2. Respond naturally and conversationally in {language_name}
        3. DO NOT ask multiple questions in one response
        4. Wait for the user to speak - don't dominate the conversation
        5. Be helpful but concise
        6. ALWAYS respond in {language_name} language
        7. If user says something brief or unclear, ask ONE clarifying question
        8. Don't repeat the same type of response multiple times
        {kb_instructions}

        Conversation history:
        {history_text}

        Current user input: {current_input}

        Provide a SHORT, helpful response that continues the conversation naturally.
        Remember: This is a voice call - keep it brief and conversational!
        """
    
    def _parse_flow_response(self, response_text: str) -> Dict[str, Any]:
        """Parse Claude's response to extract call flow configuration."""
        try:
            # Try to extract JSON from the response
            import json
            import re
            
            # Look for JSON in the response
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                parsed_flow = json.loads(json_match.group())
                # Ensure the flow supports conversation
                if 'conversation_mode' not in parsed_flow:
                    parsed_flow['conversation_mode'] = 'bidirectional'
                if 'keep_alive' not in parsed_flow:
                    parsed_flow['keep_alive'] = True
                return parsed_flow
            else:
                # If no JSON found, use conversation flow
                return self._get_conversation_flow()
        except Exception as e:
            logger.error(f"Error parsing Claude response: {str(e)}")
            return self._get_conversation_flow()
    
    def _get_default_flow(self) -> Dict[str, Any]:
        """Get default call flow configuration."""
        return {
            "type": "stream",
            "greeting": "Hello! Thank you for calling. How can I assist you today?",
            "ws_url": f"wss://localhost:5000/media-stream",
            "chunk_size": 500,
            "record": True,
            "steps": [
                {
                    "action": "speak",
                    "text": "Hello! Thank you for calling. How can I assist you today?"
                },
                {
                    "action": "listen",
                    "timeout": 30
                },
                {
                    "action": "respond",
                    "type": "dynamic"
                }
            ]
        }
    
    def _get_conversation_flow(self) -> Dict[str, Any]:
        """Get conversation-focused call flow configuration."""
        return {
            "type": "conversation",
            "initial_message": "Hello! You're now connected. Please go ahead and speak.",
            "conversation_mode": "bidirectional",
            "keep_alive": True,
            "max_duration": 1800,  # 30 minutes max
            "silence_timeout": 10,  # 10 seconds of silence before prompting
            "end_call_phrases": ["goodbye", "end call", "hang up", "bye bye"],
            "steps": [
                {
                    "action": "answer_call",
                    "auto_answer": True
                },
                {
                    "action": "play_greeting",
                    "text": "Hello! You're now connected. Please go ahead and speak.",
                    "voice": "natural"
                },
                {
                    "action": "start_conversation",
                    "mode": "continuous",
                    "enable_interruption": True,
                    "record_conversation": True
                },
                {
                    "action": "monitor_silence",
                    "timeout": 10,
                    "prompt_text": "Are you still there? Please continue speaking."
                },
                {
                    "action": "end_call_detection",
                    "phrases": ["goodbye", "end call", "hang up", "bye bye"],
                    "farewell_message": "Thank you for calling. Have a great day!"
                }
            ],
            "recording": {
                "enabled": True,
                "format": "wav",
                "quality": "high"
            },
            "audio_settings": {
                "echo_cancellation": True,
                "noise_reduction": True,
                "auto_gain_control": True
            }
        }

    def _get_language_name(self, language_code: str) -> str:
        """
        Get human-readable language name from language code.

        Args:
            language_code: Language code (e.g., 'en-IN', 'hi-IN')

        Returns:
            Human-readable language name
        """
        language_names = {
            'en-IN': 'English',
            'hi-IN': 'Hindi',
            'bn-IN': 'Bengali',
            'gu-IN': 'Gujarati',
            'kn-IN': 'Kannada',
            'ml-IN': 'Malayalam',
            'mr-IN': 'Marathi',
            'or-IN': 'Odia',
            'pa-IN': 'Punjabi',
            'ta-IN': 'Tamil',
            'te-IN': 'Telugu'
        }
        return language_names.get(language_code, 'Hindi/English mixed')

# Global instance
claude_service = ClaudeService()