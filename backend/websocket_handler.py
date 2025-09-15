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
from datetime import datetime, timedelta
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
        self.call_states: Dict[str, Dict[str, Any]] = {}
        self.silence_timers: Dict[str, asyncio.Task] = {}
        self.audio_buffers: Dict[str, list] = {}  # Buffer audio chunks
        self.processing_locks: Dict[str, asyncio.Lock] = {}  # Prevent concurrent processing
        
    async def connect(self, websocket: WebSocket, stream_id: str = None):
        """Accept WebSocket connection and store it"""
        await websocket.accept()
        connection_id = stream_id or f"conn_{datetime.now().timestamp()}"
        self.active_connections[connection_id] = websocket
        self.conversation_history[connection_id] = []
        self.audio_buffers[connection_id] = []
        self.processing_locks[connection_id] = asyncio.Lock()
        
        # Initialize call state
        self.call_states[connection_id] = {
            'status': 'connected',
            'last_user_speech': None,
            'last_ai_response': None,
            'waiting_for_user': True,
            'greeting_sent': False,
            'call_ended': False,
            'silence_warnings': 0,
            'max_silence_warnings': 2,
            'is_processing': False,
            'last_meaningful_speech': None
        }
        
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
            
        if connection_id in self.call_states:
            del self.call_states[connection_id]
            
        if connection_id in self.audio_buffers:
            del self.audio_buffers[connection_id]
            
        if connection_id in self.processing_locks:
            del self.processing_locks[connection_id]
            
        # Cancel silence timer if exists
        if connection_id in self.silence_timers:
            self.silence_timers[connection_id].cancel()
            del self.silence_timers[connection_id]
            
        logger.info(f"WebSocket disconnected: {connection_id}")
    
    async def handle_incoming_message(self, websocket: WebSocket, message: str, connection_id: str):
        """
        Handle incoming messages from Teler
        
        Message types:
        - start: Stream metadata
        - audio: Audio chunk from Teler
        """
        try:
            # Check if call has ended - FIRST CHECK
            call_state = self.call_states.get(connection_id, {})
            if call_state.get('call_ended', False):
                logger.debug(f"Ignoring message for ended call: {connection_id}")
                return
                
            data = json.loads(message)
            message_type = data.get("type")
            
            logger.debug(f"Received WebSocket message type: {message_type} for connection: {connection_id}")
            
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
        
        # Update call state
        if connection_id in self.call_states:
            self.call_states[connection_id]['status'] = 'active'
        
        # Send initial greeting after a short delay
        await asyncio.sleep(1)  # Give time for connection to stabilize
        await self._send_initial_greeting(connection_id)
        
        # Start silence monitoring
        await self._start_silence_monitoring(connection_id)
    
    async def _handle_audio_message(self, data: Dict[str, Any], connection_id: str, websocket: WebSocket):
        """Handle incoming audio chunk from Teler - BUFFER APPROACH"""
        # Check if call has ended - CRITICAL CHECK
        call_state = self.call_states.get(connection_id, {})
        if call_state.get('call_ended', False):
            logger.debug(f"🚫 Ignoring audio for ended call: {connection_id}")
            return
            
        stream_id = data.get("stream_id")
        message_id = data.get("message_id")
        audio_b64 = data.get("data", {}).get("audio_b64")
        
        if not audio_b64:
            logger.warning("Received audio message without audio data")
            return
        
        logger.debug(f"🎤 Buffering audio chunk {message_id} for stream {stream_id}")
        
        # Add to audio buffer instead of processing immediately
        if connection_id in self.audio_buffers:
            self.audio_buffers[connection_id].append({
                'audio_b64': audio_b64,
                'message_id': message_id,
                'timestamp': datetime.now()
            })
        
        # Only process if we're waiting for user input and not already processing
        if (call_state.get('waiting_for_user', True) and 
            not call_state.get('is_processing', False)):
            
            # Start processing after a short delay to accumulate more audio
            await asyncio.sleep(0.5)  # Wait 500ms to accumulate audio
            await self._process_accumulated_audio(connection_id, websocket)
    
    async def _process_accumulated_audio(self, connection_id: str, websocket: WebSocket):
        """Process accumulated audio chunks"""
        # Use lock to prevent concurrent processing
        async with self.processing_locks.get(connection_id, asyncio.Lock()):
            call_state = self.call_states.get(connection_id, {})
            
            # Double check call hasn't ended
            if call_state.get('call_ended', False):
                logger.debug(f"🚫 Call ended during processing: {connection_id}")
                return
                
            # Check if already processing
            if call_state.get('is_processing', False):
                logger.debug(f"⏳ Already processing audio for: {connection_id}")
                return
            
            # Mark as processing
            if connection_id in self.call_states:
                self.call_states[connection_id]['is_processing'] = True
            
            try:
                # Get accumulated audio chunks
                audio_chunks = self.audio_buffers.get(connection_id, [])
                if not audio_chunks:
                    return
                
                logger.info(f"🔄 Processing {len(audio_chunks)} accumulated audio chunks for {connection_id}")
                
                # Combine audio chunks
                combined_audio = self._combine_audio_chunks(audio_chunks)
                
                # Clear the buffer
                self.audio_buffers[connection_id] = []
                
                # Process the combined audio
                transcript = await self._convert_audio_to_text(combined_audio, connection_id)
                
                if transcript and self._is_meaningful_speech(transcript):
                    logger.info(f"📝 USER SAID: '{transcript}' (Connection: {connection_id})")
                    
                    # Update call state - user has spoken meaningfully
                    if connection_id in self.call_states:
                        self.call_states[connection_id]['last_user_speech'] = datetime.now()
                        self.call_states[connection_id]['last_meaningful_speech'] = transcript
                        self.call_states[connection_id]['waiting_for_user'] = False
                        self.call_states[connection_id]['silence_warnings'] = 0
                    
                    # Add to conversation history
                    if connection_id not in self.conversation_history:
                        self.conversation_history[connection_id] = []
                    
                    self.conversation_history[connection_id].append({
                        "role": "user",
                        "content": transcript
                    })
                    
                    # Generate and send AI response
                    await self._generate_and_send_ai_response(transcript, connection_id, websocket)
                    
                    # Reset silence monitoring
                    await self._reset_silence_monitoring(connection_id)
                else:
                    logger.debug(f"🔇 No meaningful speech detected in accumulated audio for {connection_id}")
                    
            except Exception as e:
                logger.error(f"❌ Error processing accumulated audio: {e}")
            finally:
                # Mark as not processing
                if connection_id in self.call_states:
                    self.call_states[connection_id]['is_processing'] = False
    
    def _combine_audio_chunks(self, audio_chunks: list) -> str:
        """Combine multiple audio chunks into one"""
        try:
            combined_data = b''
            for chunk in audio_chunks:
                audio_data = base64.b64decode(chunk['audio_b64'])
                combined_data += audio_data
            
            # Encode back to base64
            return base64.b64encode(combined_data).decode('utf-8')
        except Exception as e:
            logger.error(f"Error combining audio chunks: {e}")
            # Return the first chunk if combination fails
            return audio_chunks[0]['audio_b64'] if audio_chunks else ""
    
    async def _convert_audio_to_text(self, audio_b64: str, connection_id: str) -> Optional[str]:
        """Convert audio to text using Sarvam AI"""
        try:
            
            # Convert speech to text using Sarvam AI
            logger.debug("🎯 Converting accumulated speech to text with Sarvam AI...")
            transcript = await sarvam_service.speech_to_text(audio_b64, language="en-IN")
            
            if transcript and transcript.strip():
                logger.info(f"📝 STT Result: '{transcript}' (Connection: {connection_id})")
                return transcript.strip()
            else:
                logger.debug(f"🔇 No speech detected in accumulated audio")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error converting audio to text: {e}")
            return None
    
    async def _generate_and_send_ai_response(self, user_input: str, connection_id: str, websocket: WebSocket):
        """Generate AI response and send it back"""
        try:
            # Generate AI response using Claude
            logger.info("🤖 Generating AI response with Claude...")
            ai_response = await self._generate_ai_response(user_input, connection_id)
            
            if not ai_response:
                ai_response = "मैं समझ गया। कृपया आगे बताएं।"  # "I understand. Please continue."
            
            logger.info(f"💬 AI Response: '{ai_response}'")
            
            # Add AI response to conversation history
            self.conversation_history[connection_id].append({
                "role": "assistant",
                "content": ai_response
            })
            
            # Convert AI response to speech using Sarvam AI
            logger.info("🔊 Converting AI response to speech with Sarvam AI...")
            response_audio = await sarvam_service.text_to_speech(
                text=ai_response,
                language="en-IN",
                speaker="meera"
            )
            
            if response_audio:
                await self._send_audio_response(websocket, response_audio)
                logger.info("✅ AI response sent successfully")
                
                # Update call state - now waiting for user again
                if connection_id in self.call_states:
                    self.call_states[connection_id]['waiting_for_user'] = True
                    self.call_states[connection_id]['last_ai_response'] = datetime.now()
            else:
                logger.error("❌ Failed to generate response audio")
                
        except Exception as e:
            logger.error(f"❌ Error generating and sending AI response: {e}")
    
    async def _send_initial_greeting(self, connection_id: str):
        """Send initial greeting audio to the caller"""
        websocket = self.active_connections.get(connection_id)
        call_state = self.call_states.get(connection_id, {})
        
        if not websocket or call_state.get('greeting_sent', False) or call_state.get('call_ended', False):
            return
        
        # Mark greeting as sent
        if connection_id in self.call_states:
            self.call_states[connection_id]['greeting_sent'] = True
            self.call_states[connection_id]['waiting_for_user'] = True
        
        greeting_text = "नमस्ते! मैं आपकी सहायता के लिए यहाँ हूँ। कृपया बताएं कि मैं आपकी कैसे मदद कर सकती हूँ?"
        
        # Generate greeting audio using Sarvam AI TTS
        greeting_audio = await sarvam_service.text_to_speech(
            text=greeting_text,
            language="en-IN",
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
                logger.info(f"✅ Sent greeting to connection {connection_id}")
                
                # Update call state
                if connection_id in self.call_states:
                    self.call_states[connection_id]['last_ai_response'] = datetime.now()
                    
            except Exception as e:
                logger.error(f"Failed to send greeting: {e}")
        else:
            logger.warning("Failed to generate greeting audio with Sarvam AI")
    
    def _convert_audio_format(self, audio_b64: str) -> str:
        """Convert Teler audio format to format suitable for Sarvam AI"""
        try:
            # Decode base64 audio
            audio_data = base64.b64decode(audio_b64)
            
            # Create WAV format for Sarvam AI
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
    
    def _is_meaningful_speech(self, transcript: str) -> bool:
        """Check if the transcript contains meaningful speech"""
        if not transcript or not transcript.strip():
            return False
            
        # Remove common filler words and check length
        cleaned = transcript.strip().lower()
        
        # Ignore very short utterances or common fillers
        filler_words = ['so', 'um', 'uh', 'hmm', 'ah', 'er', 'well', 'and', 'the', 'but', 'oh']
        
        # If it's just a filler word, don't consider it meaningful
        if cleaned in filler_words:
            logger.debug(f"Ignoring filler word: '{cleaned}'")
            return False
            
        # If it's very short (less than 4 characters), likely not meaningful
        if len(cleaned) < 4:
            logger.debug(f"Ignoring short utterance: '{cleaned}'")
            return False
            
        # If it's the same word repeated, might be noise
        words = cleaned.split()
        if len(words) == 1 and len(words[0]) < 5:
            logger.debug(f"Ignoring single short word: '{cleaned}'")
            return False
        
        # Check if it's a meaningful sentence (has at least 2 words or one long word)
        if len(words) >= 2 or (len(words) == 1 and len(words[0]) >= 5):
            return True
            
        return False
    
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
                    'platform': 'teler',
                    'instruction': 'Keep responses very short (1-2 sentences max). Wait for user to speak. Listen more, talk less.'
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
    
    async def _start_silence_monitoring(self, connection_id: str):
        """Start monitoring for silence and handle call timeout"""
        if connection_id in self.silence_timers:
            self.silence_timers[connection_id].cancel()
        
        self.silence_timers[connection_id] = asyncio.create_task(
            self._monitor_silence(connection_id)
        )
    
    async def _reset_silence_monitoring(self, connection_id: str):
        """Reset silence monitoring timer"""
        await self._start_silence_monitoring(connection_id)
    
    async def _monitor_silence(self, connection_id: str):
        """Monitor for silence and handle timeouts"""
        try:
            while True:
                await asyncio.sleep(30)  # Check every 30 seconds
                
                call_state = self.call_states.get(connection_id, {})
                if call_state.get('call_ended', False):
                    break
                
                last_speech = call_state.get('last_user_speech')
                
                if not last_speech:
                    continue
                
                # Calculate time since last meaningful user speech
                time_since_speech = datetime.now() - last_speech
                
                # If no speech for 30 seconds, send warning or end call
                if time_since_speech.total_seconds() >= 30:
                    warnings = call_state.get('silence_warnings', 0)
                    max_warnings = call_state.get('max_silence_warnings', 2)
                    
                    if warnings < max_warnings:
                        # Send warning
                        await self._send_silence_warning(connection_id, warnings + 1)
                        if connection_id in self.call_states:
                            self.call_states[connection_id]['silence_warnings'] = warnings + 1
                    else:
                        # End call
                        await self._end_call_gracefully(connection_id)
                        break
                        
        except asyncio.CancelledError:
            logger.debug(f"Silence monitoring cancelled for {connection_id}")
        except Exception as e:
            logger.error(f"Error in silence monitoring: {e}")
    
    async def _send_silence_warning(self, connection_id: str, warning_number: int):
        """Send a silence warning to the user"""
        websocket = self.active_connections.get(connection_id)
        if not websocket:
            return
        
        if warning_number == 1:
            warning_text = "क्या आप वहाँ हैं? कृपया बोलें।"  # "Are you there? Please speak."
        else:
            warning_text = "मैं आपका इंतज़ार कर रहा हूँ। कुछ और कहना चाहते हैं?"  # "I'm waiting for you. Anything else you'd like to say?"
        
        logger.info(f"Sending silence warning {warning_number} to {connection_id}")
        
        warning_audio = await sarvam_service.text_to_speech(
            text=warning_text,
            language="en-IN",
            speaker="meera"
        )
        
        if warning_audio:
            warning_message = {
                "type": "audio",
                "audio_b64": warning_audio,
                "chunk_id": self.chunk_counter
            }
            
            self.chunk_counter += 1
            
            try:
                await websocket.send_text(json.dumps(warning_message))
                logger.info(f"✅ Sent silence warning {warning_number} to {connection_id}")
            except Exception as e:
                logger.error(f"Failed to send silence warning: {e}")
    
    async def _end_call_gracefully(self, connection_id: str):
        """End the call gracefully with a thank you message"""
        websocket = self.active_connections.get(connection_id)
        if not websocket:
            return
        
        # Mark call as ended
        if connection_id in self.call_states:
            self.call_states[connection_id]['call_ended'] = True
            self.call_states[connection_id]['status'] = 'ended'
        
        farewell_text = "धन्यवाद आपने कॉल किया। आपका दिन शुभ हो। नमस्ते!"  # "Thank you for calling. Have a good day. Goodbye!"
        
        logger.info(f"Ending call gracefully for {connection_id}")
        
        farewell_audio = await sarvam_service.text_to_speech(
            text=farewell_text,
            language="en-IN",
            speaker="meera"
        )
        
        if farewell_audio:
            farewell_message = {
                "type": "audio",
                "audio_b64": farewell_audio,
                "chunk_id": self.chunk_counter
            }
            
            self.chunk_counter += 1
            
            try:
                await websocket.send_text(json.dumps(farewell_message))
                logger.info(f"✅ Sent farewell message to {connection_id}")
                
                # Wait a bit for the message to be sent, then close
                await asyncio.sleep(3)
                
            except Exception as e:
                logger.error(f"Failed to send farewell message: {e}")
        
        # Cancel silence timer
        if connection_id in self.silence_timers:
            self.silence_timers[connection_id].cancel()
            del self.silence_timers[connection_id]
        
        # Close the WebSocket connection
        try:
            await websocket.close(code=1000, reason="Call ended due to inactivity")
            logger.info(f"✅ Closed WebSocket connection for {connection_id}")
        except Exception as e:
            logger.error(f"Error closing WebSocket: {e}")
    
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