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
        if not self.api_key or not ANTHROPIC_AVAILABLE:
            if not self.api_key:
                logger.warning("ANTHROPIC_API_KEY not found, Claude features will be disabled")
            if not ANTHROPIC_AVAILABLE:
                logger.warning("Anthropic library not available, Claude features will be disabled")
            self.client = None
        else:
            try:
                self.client = Anthropic(api_key=self.api_key)
                logger.info("Claude service initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize Claude service: {str(e)}")
                self.client = None
    
    def is_available(self) -> bool:
        """Check if Claude service is available."""
        return self.client is not None and ANTHROPIC_AVAILABLE and self.api_key is not None
    
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
            prompt = self._build_conversation_prompt(conversation_context)
            
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
    
    def _build_conversation_prompt(self, conversation_context: Dict[str, Any]) -> str:
        """Build prompt for conversation response generation."""
        history = conversation_context.get('history', [])
        current_input = conversation_context.get('current_input', '')
        
        history_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in history])
        
        return f"""
        You are an AI assistant helping with a voice call conversation. 
        
        Conversation history:
        {history_text}
        
        Current user input: {current_input}
        
        Please provide a helpful, professional, and engaging response that continues the conversation naturally.
        Keep responses concise and appropriate for a voice call context.
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

# Global instance
claude_service = ClaudeService()