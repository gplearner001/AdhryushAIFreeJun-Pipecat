#!/usr/bin/env python3
"""
WebSocket handler for Teler audio streaming
Implements bidirectional audio streaming between Teler and the application
"""

import json
import logging
import asyncio
from typing import Dict, Any, Optional
from fastapi import WebSocket, WebSocketDisconnect
from datetime import datetime
from audio_processor import audio_processor
from claude_service import claude_service

logger = logging.getLogger(__name__)

class TelerWebSocketHandler:
    """Handles WebSocket connections and audio streaming with Teler"""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.stream_metadata: Dict[str, Dict[str, Any]] = {}
        self.chunk_counter = 1
        
    async def connect(self, websocket: WebSocket, stream_id: str = None):
        """Accept WebSocket connection and store it"""
        await websocket.accept()
        connection_id = stream_id or f"conn_{datetime.now().timestamp()}"
        self.active_connections[connection_id] = websocket
        logger.info(f"WebSocket connected: {connection_id}")
        return connection_id
    
    def disconnect(self, connection_id: str):
        """Remove WebSocket connection"""
        if connection_id in self.active_connections:
            del self.active_connections[connection_id]
            logger.info(f"WebSocket disconnected: {connection_id}")
    
    async def handle_incoming_message(self, websocket: WebSocket, message: str, connection_id: str):
        """
        Handle incoming messages from Teler
        
        Message types:
        - start: Stream metadata
        - audio: Audio chunk from Teler
        """
        try:
            data = json.loads(message)
            message_type = data.get("type")
            
            if message_type == "start":
                await self._handle_start_message(data, connection_id)
            elif message_type == "audio":
                await self._handle_audio_message(data, connection_id, websocket)
            else:
                logger.warning(f"Unknown message type: {message_type}")
                
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON message: {e}")
        except Exception as e:
            logger.error(f"Error handling message: {e}")
    
    async def _handle_start_message(self, data: Dict[str, Any], connection_id: str):
        """Handle start message with stream metadata"""
        logger.info(f"Stream started for connection {connection_id}")
        
        # Store stream metadata
        self.stream_metadata[connection_id] = {
            "account_id": data.get("account_id"),
            "call_app_id": data.get("call_app_id"),
            "call_id": data.get("call_id"),
            "stream_id": data.get("stream_id"),
            "encoding": data.get("data", {}).get("encoding", "audio/l16"),
            "sample_rate": data.get("data", {}).get("sample_rate", 8000),
            "channels": data.get("data", {}).get("channels", 1),
            "started_at": datetime.now().isoformat()
        }
        
        logger.info(f"Stream metadata: {self.stream_metadata[connection_id]}")
        
        # Send initial response or greeting
        await self._send_initial_greeting(connection_id)
    
    async def _handle_audio_message(self, data: Dict[str, Any], connection_id: str, websocket: WebSocket):
        """Handle incoming audio chunk from Teler"""
        stream_id = data.get("stream_id")
        message_id = data.get("message_id")
        audio_b64 = data.get("data", {}).get("audio_b64")
        
        if not audio_b64:
            logger.warning("Received audio message without audio data")
            return
        
        logger.debug(f"Received audio chunk {message_id} for stream {stream_id}")
        
        # Convert audio to text using STT
        stream_metadata = self.stream_metadata.get(connection_id, {})
        encoding = stream_metadata.get("encoding", "audio/l16")
        sample_rate = stream_metadata.get("sample_rate", 8000)
        
        transcribed_text = await audio_processor.base64_to_text(audio_b64, encoding, sample_rate)
        
        if transcribed_text:
            logger.info(f"User said: '{transcribed_text}'")
            
            # Generate AI response using Claude
            response_text = await self._generate_ai_response(transcribed_text, connection_id)
            
            if response_text:
                # Convert AI response to audio using TTS
                response_audio_b64 = await audio_processor.text_to_base64(response_text, encoding, sample_rate)
                
                if response_audio_b64:
                    # Send audio response back to Teler
                    await self._send_audio_response(websocket, response_audio_b64)
                else:
                    logger.warning("Failed to convert AI response to audio")
            else:
                logger.warning("No AI response generated")
        else:
            logger.debug("No speech detected in audio chunk")
    
    async def _generate_ai_response(self, user_text: str, connection_id: str) -> Optional[str]:
        """
        Generate AI response using Claude based on user speech
        
        Args:
            user_text: Transcribed user speech
            connection_id: WebSocket connection ID
            
        Returns:
            AI generated response text
        """
        try:
            # Get conversation history for this connection
            if not hasattr(self, 'conversation_history'):
                self.conversation_history = {}
            
            if connection_id not in self.conversation_history:
                self.conversation_history[connection_id] = []
            
            # Add user message to history
            self.conversation_history[connection_id].append({
                "role": "user",
                "content": user_text
            })
            
            # Generate AI response
            conversation_context = {
                "history": self.conversation_history[connection_id],
                "current_input": user_text,
                "call_id": self.stream_metadata.get(connection_id, {}).get("call_id"),
                "context": {
                    "source": "voice_call",
                    "connection_id": connection_id,
                    "stream_metadata": self.stream_metadata.get(connection_id, {})
                }
            }
            
            if claude_service.is_available():
                response_text = await claude_service.generate_conversation_response(conversation_context)
            else:
                # Fallback response when Claude is not available
                response_text = self._get_fallback_response(user_text)
            
            # Add AI response to history
            self.conversation_history[connection_id].append({
                "role": "assistant",
                "content": response_text
            })
            
            # Limit conversation history to last 20 messages
            if len(self.conversation_history[connection_id]) > 20:
                self.conversation_history[connection_id] = self.conversation_history[connection_id][-20:]
            
            logger.info(f"AI response generated: '{response_text}'")
            return response_text
            
        except Exception as e:
            logger.error(f"Error generating AI response: {e}")
            return "I apologize, but I'm having trouble processing your request right now."
    
    def _get_fallback_response(self, user_text: str) -> str:
        """Generate fallback response when AI is not available"""
        user_text_lower = user_text.lower()
        
        if any(greeting in user_text_lower for greeting in ["hello", "hi", "hey"]):
            return "Hello! How can I help you today?"
        elif any(question in user_text_lower for question in ["how are you", "how's it going"]):
            return "I'm doing well, thank you for asking! How can I assist you?"
        elif any(thanks in user_text_lower for thanks in ["thank you", "thanks"]):
            return "You're welcome! Is there anything else I can help you with?"
        elif any(goodbye in user_text_lower for goodbye in ["goodbye", "bye", "see you"]):
            return "Goodbye! Have a great day!"
        else:
            return f"I heard you say: '{user_text}'. How can I help you with that?"
    
    async def _send_initial_greeting(self, connection_id: str):
        """Send initial greeting audio to the caller"""
        websocket = self.active_connections.get(connection_id)
        if not websocket:
            return
        
        # Generate greeting using TTS
        greeting_text = "Hello! Thank you for calling. I'm your AI assistant. How can I help you today?"
        
        stream_metadata = self.stream_metadata.get(connection_id, {})
        encoding = stream_metadata.get("encoding", "audio/l16")
        sample_rate = stream_metadata.get("sample_rate", 8000)
        
        greeting_audio_b64 = await audio_processor.text_to_base64(greeting_text, encoding, sample_rate)
        
        if greeting_audio_b64:
            greeting_message = {
                "type": "audio",
                "audio_b64": greeting_audio_b64,
                "chunk_id": self.chunk_counter
            }
            
            self.chunk_counter += 1
            
            try:
                await websocket.send_text(json.dumps(greeting_message))
                logger.info(f"Sent TTS greeting to connection {connection_id}")
            except Exception as e:
                logger.error(f"Failed to send greeting: {e}")
        else:
            logger.warning("Failed to generate greeting audio, sending placeholder")
            # Fallback to empty audio if TTS fails
            greeting_message = {
                "type": "audio",
                "audio_b64": "UklGRiQAAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQAAAAA=",
                "chunk_id": self.chunk_counter
            }
            
            self.chunk_counter += 1
            
            try:
                await websocket.send_text(json.dumps(greeting_message))
                logger.info(f"Sent placeholder greeting to connection {connection_id}")
            except Exception as e:
                logger.error(f"Failed to send greeting: {e}")
    
    def disconnect(self, connection_id: str):
        """Remove WebSocket connection and clean up conversation history"""
        if connection_id in self.active_connections:
            del self.active_connections[connection_id]
            logger.info(f"WebSocket disconnected: {connection_id}")
        
        # Clean up conversation history
        if hasattr(self, 'conversation_history') and connection_id in self.conversation_history:
            del self.conversation_history[connection_id]
            logger.info(f"Cleaned up conversation history for {connection_id}")
        
        # Clean up stream metadata
        if connection_id in self.stream_metadata:
            del self.stream_metadata[connection_id]
    
    async def _send_audio_response(self, websocket: WebSocket, audio_b64: str):
        """Send audio response back to Teler"""
        response_message = {
            "type": "audio",
            "audio_b64": audio_b64,
            "chunk_id": self.chunk_counter
        }
        
        self.chunk_counter += 1
        
        try:
            await websocket.send_text(json.dumps(response_message))
            logger.debug(f"Sent audio response chunk {self.chunk_counter - 1}")
        except Exception as e:
            logger.error(f"Failed to send audio response: {e}")
    
    async def send_interrupt(self, connection_id: str, chunk_id: int):
        """Send interrupt message to stop specific chunk playback"""
        websocket = self.active_connections.get(connection_id)
        if not websocket:
            return
        
        interrupt_message = {
            "type": "interrupt",
            "chunk_id": chunk_id
        }
        
        try:
            await websocket.send_text(json.dumps(interrupt_message))
            logger.info(f"Sent interrupt for chunk {chunk_id}")
        except Exception as e:
            logger.error(f"Failed to send interrupt: {e}")
    
    async def send_clear(self, connection_id: str):
        """Send clear message to wipe out entire buffer"""
        websocket = self.active_connections.get(connection_id)
        if not websocket:
            return
        
        clear_message = {"type": "clear"}
        
        try:
            await websocket.send_text(json.dumps(clear_message))
            logger.info("Sent clear message")
        except Exception as e:
            logger.error(f"Failed to send clear: {e}")
    
    def get_stream_info(self, connection_id: str) -> Optional[Dict[str, Any]]:
        """Get stream metadata for a connection"""
        return self.stream_metadata.get(connection_id)
    
    def get_active_streams(self) -> Dict[str, Dict[str, Any]]:
        """Get all active stream metadata"""
        return self.stream_metadata.copy()
    
    def get_conversation_history(self, connection_id: str) -> list:
        """Get conversation history for a specific connection"""
        if not hasattr(self, 'conversation_history'):
            return []
        return self.conversation_history.get(connection_id, [])

# Global instance
websocket_handler = TelerWebSocketHandler()