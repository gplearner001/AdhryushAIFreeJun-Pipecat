#!/usr/bin/env python3
"""
WebSocket handler for Teler audio streaming
Implements bidirectional audio streaming between Teler and the application
"""

import json
import logging
import asyncio
import base64
import wave
import io
from typing import Dict, Any, Optional
from fastapi import WebSocket, WebSocketDisconnect
from datetime import datetime
from sarvam_service import sarvam_service
from claude_service import claude_service

logger = logging.getLogger(__name__)

class TelerWebSocketHandler:
    """Handles WebSocket connections and audio streaming with Teler"""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.stream_metadata: Dict[str, Dict[str, Any]] = {}
        self.chunk_counter = 1
        self.conversation_history: Dict[str, list] = {}
        
    async def connect(self, websocket: WebSocket, stream_id: str = None):
        """Accept WebSocket connection and store it"""
        await websocket.accept()
        connection_id = stream_id or f"conn_{datetime.now().timestamp()}"
        self.active_connections[connection_id] = websocket
        self.conversation_history[connection_id] = []
        logger.info(f"WebSocket connected: {connection_id}")
        return connection_id
    
    def disconnect(self, connection_id: str):
        """Remove WebSocket connection"""
        if connection_id in self.active_connections:
            del self.active_connections[connection_id]
            if connection_id in self.conversation_history:
                del self.conversation_history[connection_id]
            if connection_id in self.stream_metadata:
                del self.stream_metadata[connection_id]
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
            
            logger.info(f"Received WebSocket message type: {message_type} for connection: {connection_id}")
            
            if message_type == "start":
                await self._handle_start_message(data, connection_id)
            elif message_type == "audio":
                await self._handle_audio_message(data, connection_id, websocket)
            else:
                logger.warning(f"Unknown message type: {message_type}")
                
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON message: {e}")
            logger.error(f"Raw message: {message[:200]}...")
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
        
        logger.info(f"🎤 Received audio chunk {message_id} for stream {stream_id} (size: {len(audio_b64)} chars)")
        
        # Process the audio (this is where you'd integrate with AI services, STT, etc.)
        response_audio = await self._process_audio_chunk(audio_b64, connection_id)
        
        # Send response audio back to Teler if we have any
        if response_audio:
            logger.info(f"🔊 Sending audio response back to caller")
            await self._send_audio_response(websocket, response_audio)
    
    async def _send_initial_greeting(self, connection_id: str):
        """Send initial greeting audio to the caller"""
        websocket = self.active_connections.get(connection_id)
        if not websocket:
            return
        
        # This would typically be generated by TTS or pre-recorded
        # For now, we'll simulate with a placeholder
        greeting_text = "नमस्ते! आपका स्वागत है। कृपया बोलें।"  # "Hello! Welcome. Please speak."
        
        # Generate greeting audio using Sarvam AI TTS
        greeting_audio = await sarvam_service.text_to_speech(
            text=greeting_text,
            language="hi-IN",
            speaker="meera"
        )
        
        if greeting_audio:
            greeting_message = {
                "type": "audio",
                "audio_b64": greeting_audio,
                "chunk_id": self.chunk_counter
            }
            
            self.chunk_counter += 1
            
            try:
                await websocket.send_text(json.dumps(greeting_message))
                logger.info(f"✅ Sent Sarvam AI greeting to connection {connection_id}")
            except Exception as e:
                logger.error(f"Failed to send greeting: {e}")
        else:
            logger.warning("Failed to generate greeting audio with Sarvam AI")
    
    def _convert_audio_format(self, audio_b64: str) -> str:
        """
        Convert Teler audio format to format suitable for Sarvam AI.
        Teler sends audio/l16 at 8000Hz, which should work with Sarvam AI.
        """
        
        try:
            # Decode base64 audio
            audio_data = base64.b64decode(audio_b64)
            
            # Create WAV format for Sarvam AI
            # Teler sends raw PCM data, we need to wrap it in WAV format
            wav_buffer = io.BytesIO()
            
            with wave.open(wav_buffer, 'wb') as wav_file:
                wav_file.setnchannels(1)  # Mono
                wav_file.setsampwidth(2)  # 16-bit
                wav_file.setframerate(8000)  # 8kHz sample rate
                wav_file.writeframes(audio_data)
            
            # Get WAV data and encode to base64
            wav_data = wav_buffer.getvalue()
            wav_b64 = base64.b64encode(wav_data).decode('utf-8')
            
            logger.debug(f"Converted audio: PCM {len(audio_data)} bytes -> WAV {len(wav_data)} bytes")
            return wav_b64
            
        except Exception as e:
            logger.error(f"Error converting audio format: {e}")
            return audio_b64  # Return original if conversion fails
    
    async def _process_audio_chunk(self, audio_b64: str, connection_id: str) -> Optional[str]:
        """
        Process incoming audio chunk
        
        1. Convert audio format for Sarvam AI
        2. Use Sarvam AI STT to convert to text
        3. Process with Claude AI for response
        4. Use Sarvam AI TTS to generate response audio
        5. Return base64 encoded response audio
        """
        logger.info(f"🔄 Processing audio chunk for connection {connection_id}")
        
        try:
            # Step 1: Convert audio format for Sarvam AI
            converted_audio = self._convert_audio_format(audio_b64)
            
            # Step 2: Convert speech to text using Sarvam AI
            logger.info("🎯 Converting speech to text with Sarvam AI...")
            transcript = await sarvam_service.speech_to_text(converted_audio, language="hi-IN")
            
            if not transcript or not transcript.strip():
                logger.info("No speech detected in audio chunk")
                return None
            
            logger.info(f"📝 Transcript: '{transcript}'")
            
            # Step 3: Add to conversation history
            if connection_id not in self.conversation_history:
                self.conversation_history[connection_id] = []
            
            self.conversation_history[connection_id].append({
                "role": "user",
                "content": transcript
            })
            
            # Step 4: Generate AI response using Claude
            logger.info("🤖 Generating AI response with Claude...")
            ai_response = await self._generate_ai_response(transcript, connection_id)
            
            if not ai_response:
                ai_response = "मुझे खुशी है कि आपने बात की। कृपया और बताएं।"  # "I'm glad you spoke. Please tell me more."
            
            logger.info(f"💬 AI Response: '{ai_response}'")
            
            # Add AI response to conversation history
            self.conversation_history[connection_id].append({
                "role": "assistant",
                "content": ai_response
            })
            
            # Step 5: Convert AI response to speech using Sarvam AI
            logger.info("🔊 Converting AI response to speech with Sarvam AI...")
            response_audio = await sarvam_service.text_to_speech(
                text=ai_response,
                language="hi-IN",
                speaker="meera"
            )
            
            if response_audio:
                logger.info("✅ Successfully generated response audio")
                return response_audio
            else:
                logger.error("❌ Failed to generate response audio")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error processing audio chunk: {str(e)}")
            return None
    
    async def _generate_ai_response(self, user_input: str, connection_id: str) -> Optional[str]:
        """Generate AI response using Claude based on user input and conversation history."""
        try:
            if not claude_service.is_available():
                # Fallback responses in Hindi
                fallback_responses = [
                    "धन्यवाद। आप और क्या जानना चाहते हैं?",
                    "मैं समझ गया। कृपया आगे बताएं।",
                    "यह दिलचस्प है। और क्या है?",
                    "अच्छा। आप और क्या कहना चाहते हैं?"
                ]
                import random
                return random.choice(fallback_responses)
            
            conversation_context = {
                'history': self.conversation_history.get(connection_id, []),
                'current_input': user_input,
                'call_id': connection_id,
                'context': {
                    'language': 'hindi',
                    'mode': 'voice_call',
                    'platform': 'teler'
                }
            }
            
            response = await claude_service.generate_conversation_response(conversation_context)
            return response
            
        except Exception as e:
            logger.error(f"Error generating AI response: {str(e)}")
            return "मुझे खुशी है कि आपने बात की।"  # "I'm glad you spoke."
            
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

# Global instance
websocket_handler = TelerWebSocketHandler()