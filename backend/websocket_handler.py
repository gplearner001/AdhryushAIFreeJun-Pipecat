#!/usr/bin/env python3
"""
WebSocket handler for Teler audio streaming
Implements bidirectional audio streaming between Teler and the application
"""

import json
import logging
import asyncio
import base64
from typing import Dict, Any, Optional
from fastapi import WebSocket, WebSocketDisconnect
from datetime import datetime

logger = logging.getLogger(__name__)

class TelerWebSocketHandler:
    """Handles WebSocket connections and audio streaming with Teler"""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.stream_metadata: Dict[str, Dict[str, Any]] = {}
        self.chunk_counter = 1
        self.audio_processing_enabled = True
        self.max_audio_chunks_per_second = 50  # Rate limiting
        self.last_chunk_time = {}
        
    async def connect(self, websocket: WebSocket, stream_id: str = None):
        """Accept WebSocket connection and store it"""
        await websocket.accept()
        connection_id = stream_id or f"conn_{datetime.now().timestamp()}"
        self.active_connections[connection_id] = websocket
        self.last_chunk_time[connection_id] = datetime.now()
        logger.info(f"WebSocket connected: {connection_id}")
        return connection_id
    
    def disconnect(self, connection_id: str):
        """Remove WebSocket connection"""
        if connection_id in self.active_connections:
            del self.active_connections[connection_id]
        if connection_id in self.stream_metadata:
            del self.stream_metadata[connection_id]
        if connection_id in self.last_chunk_time:
            del self.last_chunk_time[connection_id]
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
        logger.info(f"🎙️ Stream started for connection {connection_id}")
        
        # Store stream metadata
        self.stream_metadata[connection_id] = {
            "account_id": data.get("account_id"),
            "call_app_id": data.get("call_app_id"),
            "call_id": data.get("call_id"),
            "stream_id": data.get("stream_id"),
            "encoding": data.get("data", {}).get("encoding", "audio/l16"),
            "sample_rate": data.get("data", {}).get("sample_rate", 8000),
            "channels": data.get("data", {}).get("channels", 1),
            "started_at": datetime.now().isoformat(),
            "audio_chunks_received": 0,
            "last_activity": datetime.now().isoformat()
        }
        
        logger.info(f"📊 Stream metadata: Call ID: {data.get('call_id')}, Stream ID: {data.get('stream_id')}")
        logger.info(f"🔊 Audio format: {self.stream_metadata[connection_id]['encoding']} @ {self.stream_metadata[connection_id]['sample_rate']}Hz")
        
        # Send initial response or greeting
        await self._send_initial_greeting(connection_id)
    
    async def _handle_audio_message(self, data: Dict[str, Any], connection_id: str, websocket: WebSocket):
        """Handle incoming audio chunk from Teler with rate limiting"""
        stream_id = data.get("stream_id")
        message_id = data.get("message_id")
        audio_data = data.get("data", {})
        audio_b64 = audio_data.get("audio_b64")
        
        if not audio_b64:
            logger.warning("⚠️ Received audio message without audio data")
            return
        
        # Update metadata
        if connection_id in self.stream_metadata:
            self.stream_metadata[connection_id]["audio_chunks_received"] += 1
            self.stream_metadata[connection_id]["last_activity"] = datetime.now().isoformat()
            chunk_count = self.stream_metadata[connection_id]["audio_chunks_received"]
        else:
            chunk_count = 0
        
        # Rate limiting - only log every 50th chunk to reduce spam
        if chunk_count % 50 == 0:
            logger.info(f"🎵 Audio processing: Received {chunk_count} chunks for stream {stream_id}")
        
        # Only process audio if enabled and not too frequent
        current_time = datetime.now()
        if connection_id in self.last_chunk_time:
            time_diff = (current_time - self.last_chunk_time[connection_id]).total_seconds()
            if time_diff < 0.02:  # Less than 20ms since last chunk - skip processing
                return
        
        self.last_chunk_time[connection_id] = current_time
        
        # Process the audio chunk
        if self.audio_processing_enabled:
            try:
                response_audio = await self._process_audio_chunk(audio_b64, connection_id, message_id)
                
                # Send response audio back to Teler if we have any
                if response_audio:
                    await self._send_audio_response(websocket, response_audio)
            except Exception as e:
                logger.error(f"❌ Error processing audio chunk {message_id}: {e}")
    
    async def _send_initial_greeting(self, connection_id: str):
        """Send initial greeting audio to the caller"""
        websocket = self.active_connections.get(connection_id)
        if not websocket:
            return
        
        logger.info(f"👋 Sending initial greeting to connection {connection_id}")
        
        # Create a simple greeting message
        # In production, this would be actual TTS-generated audio
        greeting_message = {
            "type": "audio",
            "audio_b64": self._generate_greeting_audio(),
            "chunk_id": self.chunk_counter
        }
        
        self.chunk_counter += 1
        
        try:
            await websocket.send_text(json.dumps(greeting_message))
            logger.info(f"✅ Sent greeting to connection {connection_id}")
        except Exception as e:
            logger.error(f"❌ Failed to send greeting: {e}")
    
    async def _process_audio_chunk(self, audio_b64: str, connection_id: str, message_id: int) -> Optional[str]:
        """
        Process incoming audio chunk with proper logging and error handling
        
        This is where you would:
        1. Decode the base64 audio
        2. Convert to text using STT
        3. Process with AI/NLP
        4. Generate response text
        5. Convert to speech using TTS
        6. Return base64 encoded audio
        """
        logger.debug(f"🔄 Processing audio chunk {message_id} for connection {connection_id}")
        
        try:
            # Decode base64 audio to get raw audio data
            audio_bytes = base64.b64decode(audio_b64)
            audio_length = len(audio_bytes)
            
            # Log audio processing details (only occasionally to avoid spam)
            if message_id % 100 == 0:
                logger.info(f"🎧 Audio chunk {message_id}: {audio_length} bytes of audio data")
                logger.info(f"📈 Connection {connection_id}: Processing audio stream")
            
            # Simulate audio processing (replace with actual STT/AI/TTS pipeline)
            await self._simulate_audio_processing(audio_bytes, connection_id)
            
            # For now, return None (no response audio)
            # In production, return base64 encoded response audio
            return None
            
        except Exception as e:
            logger.error(f"❌ Error in _process_audio_chunk for message {message_id}: {e}")
            return None
    
    async def _simulate_audio_processing(self, audio_bytes: bytes, connection_id: str):
        """Simulate audio processing pipeline"""
        # This simulates the time it would take to process audio
        # In production, replace with actual STT, AI processing, and TTS
        
        # Simulate STT processing time
        await asyncio.sleep(0.001)  # 1ms processing time
        
        # Log processing simulation
        logger.debug(f"🤖 Simulated STT processing for connection {connection_id}")
        
        # Here you would:
        # 1. Use speech-to-text to convert audio_bytes to text
        # 2. Process text with AI (Claude, etc.)
        # 3. Generate response text
        # 4. Use text-to-speech to convert response to audio
        # 5. Return base64 encoded audio
    
    def _generate_greeting_audio(self) -> str:
        """Generate a simple greeting audio (placeholder)"""
        # This is a minimal WAV file header for silence
        # In production, use actual TTS to generate greeting audio
        wav_header = b'RIFF$\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00D\xac\x00\x00\x88X\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00'
        return base64.b64encode(wav_header).decode('utf-8')
    
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
            logger.info(f"📤 Sent audio response chunk {self.chunk_counter - 1}")
        except Exception as e:
            logger.error(f"❌ Failed to send audio response: {e}")
    
    async def send_interrupt(self, connection_id: str, chunk_id: int):
        """Send interrupt message to stop specific chunk playback"""
        websocket = self.active_connections.get(connection_id)
        if not websocket:
            logger.warning(f"⚠️ Cannot send interrupt: connection {connection_id} not found")
            return
        
        interrupt_message = {
            "type": "interrupt",
            "chunk_id": chunk_id
        }
        
        try:
            await websocket.send_text(json.dumps(interrupt_message))
            logger.info(f"⏹️ Sent interrupt for chunk {chunk_id}")
        except Exception as e:
            logger.error(f"❌ Failed to send interrupt: {e}")
    
    async def send_clear(self, connection_id: str):
        """Send clear message to wipe out entire buffer"""
        websocket = self.active_connections.get(connection_id)
        if not websocket:
            logger.warning(f"⚠️ Cannot send clear: connection {connection_id} not found")
            return
        
        clear_message = {"type": "clear"}
        
        try:
            await websocket.send_text(json.dumps(clear_message))
            logger.info(f"🧹 Sent clear message to connection {connection_id}")
        except Exception as e:
            logger.error(f"❌ Failed to send clear: {e}")
    
    def get_stream_info(self, connection_id: str) -> Optional[Dict[str, Any]]:
        """Get stream metadata for a connection"""
        return self.stream_metadata.get(connection_id)
    
    def get_active_streams(self) -> Dict[str, Dict[str, Any]]:
        """Get all active stream metadata"""
        return self.stream_metadata.copy()
    
    def toggle_audio_processing(self, enabled: bool):
        """Enable or disable audio processing"""
        self.audio_processing_enabled = enabled
        logger.info(f"🔧 Audio processing {'enabled' if enabled else 'disabled'}")
    
    def get_connection_stats(self, connection_id: str) -> Dict[str, Any]:
        """Get statistics for a specific connection"""
        if connection_id not in self.stream_metadata:
            return {}
        
        metadata = self.stream_metadata[connection_id]
        return {
            "connection_id": connection_id,
            "call_id": metadata.get("call_id"),
            "stream_id": metadata.get("stream_id"),
            "audio_chunks_received": metadata.get("audio_chunks_received", 0),
            "started_at": metadata.get("started_at"),
            "last_activity": metadata.get("last_activity"),
            "encoding": metadata.get("encoding"),
            "sample_rate": metadata.get("sample_rate")
        }

# Global instance
websocket_handler = TelerWebSocketHandler()