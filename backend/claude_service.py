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
    
    async def generate_call_flow(self, call_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate a dynamic call flow based on call context using Claude.
        
        Args:
            call_context: Dictionary containing call information
            
        Returns:
            Dictionary containing the generated call flow
        """
        if not self.is_available():
            return self._get_default_flow()
        
        try:
            prompt = self._build_flow_generation_prompt(call_context)
            
            response = self.client.messages.create(
                model="claude-3-sonnet-20240229",
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
            return self._get_default_flow()
    
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
                model="claude-3-sonnet-20240229",
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
        Generate a call flow configuration for a voice call with the following context:
        
        From: {call_context.get('from_number', 'Unknown')}
        To: {call_context.get('to_number', 'Unknown')}
        Purpose: {call_context.get('purpose', 'General call')}
        
        Please provide a JSON configuration that includes:
        1. Initial greeting message
        2. Call flow steps
        3. Response handling
        4. Recording preferences
        
        Format the response as a valid JSON object that can be used for call flow configuration.
        Focus on creating a professional and engaging call experience.
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
                return json.loads(json_match.group())
            else:
                # If no JSON found, create a basic flow with the response as greeting
                return {
                    "type": "stream",
                    "greeting": response_text[:200],  # First 200 chars as greeting
                    "ws_url": f"wss://localhost:5000/media-stream",
                    "chunk_size": 500,
                    "record": True
                }
        except Exception as e:
            logger.error(f"Error parsing Claude response: {str(e)}")
            return self._get_default_flow()
    
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

# Global instance
claude_service = ClaudeService()