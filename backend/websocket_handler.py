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
from vad_processor import vad_processor

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
            'last_meaningful_speech': None,
            'current_language': 'en-IN',
            'detected_language': None,
            'knowledge_base_id': None
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
        logger.info(f"🔍 FULL START MESSAGE DATA: {json.dumps(data, indent=2)}")

        call_id = data.get("call_id")
        stream_id = data.get("stream_id")
        account_id = data.get("account_id")
        call_app_id = data.get("call_app_id")

        logger.info(f"🔍 Extracted IDs - call_id: {call_id}, stream_id: {stream_id}, account_id: {account_id}, call_app_id: {call_app_id}")

        # Store stream metadata
        self.stream_metadata[connection_id] = {
            "account_id": account_id,
            "call_app_id": call_app_id,
            "call_id": call_id,
            "stream_id": stream_id,
            "encoding": data.get("data", {}).get("encoding", "audio/l16"),
            "sample_rate": data.get("data", {}).get("sample_rate", 8000),
            "channels": data.get("data", {}).get("channels", 1),
            "started_at": datetime.now().isoformat()
        }

        logger.info(f"Stream metadata: {self.stream_metadata[connection_id]}")

        # Look up knowledge base ID from call history using multiple identifiers
        knowledge_base_id = self._get_knowledge_base_for_call(call_id, stream_id, account_id)
        if knowledge_base_id:
            logger.info(f"✅ Knowledge base {knowledge_base_id} associated with call {call_id}")
        else:
            logger.warning(f"⚠️ No knowledge base found for call {call_id}")

        # Update call state
        if connection_id in self.call_states:
            self.call_states[connection_id]['status'] = 'active'
            self.call_states[connection_id]['knowledge_base_id'] = knowledge_base_id
            logger.info(f"📋 Call state updated - KB ID: {knowledge_base_id}")
        
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

        # Decode to check size
        audio_data = base64.b64decode(audio_b64)
        duration_ms = (len(audio_data) / 2) / 8  # 16-bit samples at 8kHz

        logger.debug(f"🎤 Buffering audio chunk {message_id} for stream {stream_id} ({len(audio_data)} bytes, ~{duration_ms:.1f}ms)")

        # Add to audio buffer instead of processing immediately
        if connection_id in self.audio_buffers:
            self.audio_buffers[connection_id].append({
                'audio_b64': audio_b64,
                'message_id': message_id,
                'timestamp': datetime.now(),
                'duration_ms': duration_ms
            })

        # Only process if we're waiting for user input and not already processing
        if (call_state.get('waiting_for_user', True) and
            not call_state.get('is_processing', False)):

            # Check accumulated duration
            accumulated_duration = sum(chunk.get('duration_ms', 0) for chunk in self.audio_buffers[connection_id])

            # Wait until we have at least 3 seconds of audio before processing
            if accumulated_duration >= 3000:  # 3 second minimum
                logger.info(f"✅ Accumulated {accumulated_duration:.0f}ms of audio, processing now...")
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
                
                # Calculate total duration
                total_duration_ms = sum(chunk.get('duration_ms', 0) for chunk in audio_chunks)
                logger.info(f"🔄 Processing {len(audio_chunks)} accumulated audio chunks for {connection_id} (total: {total_duration_ms:.0f}ms)")

                # Combine audio chunks
                combined_audio = self._combine_audio_chunks(audio_chunks)
                
                # Clear the buffer
                self.audio_buffers[connection_id] = []
                
                # 🎯 SPEECH DETECTION: Check if combined audio contains speech using WebRTC VAD
                logger.info(f"🔍 Checking for speech in combined audio using WebRTC VAD...")
                has_speech = vad_processor.has_speech(combined_audio)
                
                if not has_speech:
                    logger.info(f"🔇 No speech detected in audio chunk, skipping STT processing for {connection_id}")
                    
                    # Get VAD statistics for debugging
                    vad_stats = vad_processor.get_vad_stats(combined_audio)
                    logger.debug(f"📊 VAD Stats: {vad_stats}")
                    
                    return  # Skip STT processing for non-speech audio
                
                logger.info(f"🗣️ Speech detected! Proceeding with STT processing for {connection_id}")
                
                # Optional: Filter audio to keep only speech segments
                filtered_audio = vad_processor.filter_speech_audio(combined_audio)
                if filtered_audio:
                    logger.info(f"🎯 Using filtered speech-only audio for STT")
                    combined_audio = filtered_audio
                else:
                    logger.info(f"⚠️ Speech filtering returned empty, using original audio")
                
                # Get current language for this connection
                current_language = self.call_states.get(connection_id, {}).get('current_language', 'en-IN')

                # Process the combined audio with language detection
                stt_result = await self._convert_audio_to_text(combined_audio, connection_id, current_language)

                if stt_result and stt_result.get('transcript') and self._is_meaningful_speech(stt_result['transcript']):
                    transcript = stt_result['transcript']
                    detected_language = stt_result.get('language', current_language)
                    logger.info(f"📝 USER SAID: '{transcript}' (Language: {detected_language}, Connection: {connection_id})")

                    # Check for language switch request
                    switch_language = sarvam_service.detect_language_switch_request(transcript)
                    if switch_language:
                        logger.info(f"🌐 Language switch requested: {current_language} -> {switch_language}")
                        if connection_id in self.call_states:
                            self.call_states[connection_id]['current_language'] = switch_language
                        await self._send_language_switch_confirmation(connection_id, websocket, switch_language)
                        return

                    # Detect language from transcript for auto-switching
                    detected_text_language = await sarvam_service.detect_language_from_text(transcript)
                    if detected_text_language and detected_text_language != current_language:
                        logger.info(f"🌐 Auto language switch detected: {current_language} -> {detected_text_language}")
                        if connection_id in self.call_states:
                            self.call_states[connection_id]['current_language'] = detected_text_language
                            self.call_states[connection_id]['detected_language'] = detected_text_language

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
                    logger.debug(f"🔇 Speech detected but no meaningful transcript generated for {connection_id}")
                    
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

            # Calculate audio characteristics for debugging
            duration_ms = (len(combined_data) / 2) / 8  # 16-bit samples at 8kHz

            # Calculate RMS and peak for audio analysis
            import struct
            samples = struct.unpack(f'<{len(combined_data)//2}h', combined_data)
            rms = (sum(s*s for s in samples) / len(samples)) ** 0.5 if samples else 0
            peak = max(abs(s) for s in samples) if samples else 0

            logger.info(f"🔍 Analyzing combined audio characteristics...")
            logger.info(f"📊 Audio Info: RMS={rms:.2f}, Peak={peak}, Duration={duration_ms:.1f}ms")

            # Encode back to base64
            return base64.b64encode(combined_data).decode('utf-8')
        except Exception as e:
            logger.error(f"Error combining audio chunks: {e}")
            # Return the first chunk if combination fails
            return audio_chunks[0]['audio_b64'] if audio_chunks else ""
    
    async def _convert_audio_to_text(self, audio_b64: str, connection_id: str, language: str = "en-IN") -> Optional[Dict[str, Any]]:
        """Convert audio to text using Sarvam AI"""
        try:
            logger.info(f"🎯 Converting speech audio to text for connection: {connection_id} (language: {language})")
            logger.debug(f"Audio data length: {len(audio_b64)} base64 characters")

            # Get VAD statistics for logging
            vad_stats = vad_processor.get_vad_stats(audio_b64)
            logger.info(f"📊 Final VAD Stats before STT: speech_ratio={vad_stats.get('speech_ratio', 0):.2f}, speech_duration={vad_stats.get('speech_duration_ms', 0)}ms")

            # Convert speech to text using Sarvam AI with specified language
            logger.info(f"🎯 Converting speech-validated audio to text with Sarvam AI (language: {language})...")
            stt_result = await sarvam_service.speech_to_text(audio_b64, language=language)

            if stt_result and stt_result.get('transcript') and stt_result['transcript'].strip():
                logger.info(f"📝 STT Result: '{stt_result['transcript']}' (Language: {stt_result.get('language')}, Connection: {connection_id})")
                return {
                    'transcript': stt_result['transcript'].strip(),
                    'language': stt_result.get('language', language)
                }
            else:
                logger.info(f"🔇 STT returned empty result despite speech detection for {connection_id}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error converting audio to text: {e}")
            return None
    
    async def _generate_and_send_ai_response(self, user_input: str, connection_id: str, websocket: WebSocket):
        """Generate AI response and send it back"""
        try:
            # Get current language for this connection
            current_language = self.call_states.get(connection_id, {}).get('current_language', 'en-IN')

            # Generate AI response using Claude
            logger.info(f"🤖 Generating AI response with Claude (language: {current_language})...")
            ai_response = await self._generate_ai_response(user_input, connection_id)

            if not ai_response:
                # Default fallback based on language
                if current_language == 'en-IN':
                    ai_response = "I understand. Please continue."
                else:
                    ai_response = "मैं समझ गया। कृपया आगे बताएं।"  # Hindi fallback

            logger.info(f"💬 AI Response: '{ai_response}' (Language: {current_language})")

            # Add AI response to conversation history
            self.conversation_history[connection_id].append({
                "role": "assistant",
                "content": ai_response
            })

            # Get appropriate speaker for language
            speaker = self._get_speaker_for_language(current_language)

            # Convert AI response to speech using Sarvam AI with current language
            logger.info(f"🔊 Converting AI response to speech with Sarvam AI (language: {current_language}, speaker: {speaker})...")
            response_audio = await sarvam_service.text_to_speech(
                text=ai_response,
                language=current_language,
                speaker=speaker
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

        # Get current language
        current_language = self.call_states.get(connection_id, {}).get('current_language', 'en-IN')

        # Greeting text based on language
        if current_language == 'en-IN':
            greeting_text = "Hello! I am here to help you. Please tell me how I can assist you?"
        else:
            greeting_text = "नमस्ते! मैं आपकी सहायता के लिए यहाँ हूँ। कृपया बताएं कि मैं आपकी कैसे मदद कर सकती हूँ?"

        # Get appropriate speaker
        speaker = self._get_speaker_for_language(current_language)

        # Generate greeting audio using Sarvam AI TTS
        greeting_audio = await sarvam_service.text_to_speech(
            text=greeting_text,
            language=current_language,
            speaker=speaker
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
            # Get current language
            current_language = self.call_states.get(connection_id, {}).get('current_language', 'en-IN')

            if not claude_service.is_available():
                # Fallback responses based on language
                if current_language == 'en-IN':
                    fallback_responses = [
                        "Thank you. What else would you like to know?",
                        "I understand. Please continue.",
                        "That's interesting. What else?",
                        "Okay. What else would you like to say?"
                    ]
                else:
                    fallback_responses = [
                        "धन्यवाद। आप और क्या जानना चाहते हैं?",
                        "मैं समझ गया। कृपया आगे बताएं।",
                        "यह दिलचस्प है। और क्या है?",
                        "अच्छा। आप और क्या कहना चाहते हैं?"
                    ]
                import random
                return random.choice(fallback_responses)

            # Get knowledge base ID for this call
            knowledge_base_id = self.call_states.get(connection_id, {}).get('knowledge_base_id')
            logger.info(f"Using knowledge base ID: {knowledge_base_id} for AI response")

            conversation_context = {
                'history': self.conversation_history.get(connection_id, []),
                'current_input': user_input,
                'call_id': connection_id,
                'knowledge_base_id': knowledge_base_id,
                'context': {
                    'language': current_language,
                    'mode': 'voice_call',
                    'platform': 'teler',
                    'instruction': 'Keep responses very short (1-2 sentences max). Wait for user to speak. Listen more, talk less.'
                }
            }
            
            response = await claude_service.generate_conversation_response(conversation_context)
            return response
            
        except Exception as e:
            logger.error(f"Error generating AI response: {str(e)}")
            # Return fallback based on current language
            current_language = self.conversation_history.get(connection_id, [{}])[-1].get('language', 'en-IN') if connection_id in self.conversation_history else 'hi-IN'
            if current_language == 'en-IN':
                return "I'm glad you spoke."
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
    
    def _get_speaker_for_language(self, language: str) -> str:
        """
        Get appropriate speaker for the given language.

        Args:
            language: Language code (e.g., 'en-IN', 'hi-IN')

        Returns:
            Speaker name for Sarvam AI TTS
        """
        speaker_map = {
            'en-IN': 'meera',
            'hi-IN': 'meera',
            'bn-IN': 'meera',
            'gu-IN': 'meera',
            'kn-IN': 'meera',
            'ml-IN': 'meera',
            'mr-IN': 'meera',
            'or-IN': 'meera',
            'pa-IN': 'meera',
            'ta-IN': 'meera',
            'te-IN': 'meera'
        }
        return speaker_map.get(language, 'meera')

    async def _send_language_switch_confirmation(self, connection_id: str, websocket: WebSocket, new_language: str):
        """
        Send confirmation message when language is switched.

        Args:
            connection_id: Connection identifier
            websocket: WebSocket connection
            new_language: New language code
        """
        try:
            # Confirmation messages in different languages
            confirmations = {
                'en-IN': "I will now speak in English. How can I help you?",
                'hi-IN': "मैं अब हिंदी में बोलूंगी। मैं आपकी कैसे मदद कर सकती हूं?",
                'bn-IN': "আমি এখন বাংলায় কথা বলব। আমি আপনাকে কিভাবে সাহায্য করতে পারি?",
                'gu-IN': "હું હવે ગુજરાતીમાં બોલીશ. હું તમારી કેવી રીતે મદદ કરી શકું?",
                'kn-IN': "ನಾನು ಈಗ ಕನ್ನಡದಲ್ಲಿ ಮಾತನಾಡುತ್ತೇನೆ. ನಾನು ನಿಮಗೆ ಹೇಗೆ ಸಹಾಯ ಮಾಡಬಹುದು?",
                'ml-IN': "ഞാൻ ഇപ്പോൾ മലയാളത്തിൽ സംസാരിക്കും. ഞാൻ നിങ്ങളെ എങ്ങനെ സഹായിക്കും?",
                'mr-IN': "मी आता मराठीत बोलेन. मी तुम्हाला कशी मदत करू शकते?",
                'or-IN': "ମୁଁ ବର୍ତ୍ତମାନ ଓଡ଼ିଆରେ କହିବି। ମୁଁ ଆପଣଙ୍କୁ କିପରି ସାହାଯ୍ୟ କରିପାରିବି?",
                'pa-IN': "ਮੈਂ ਹੁਣ ਪੰਜਾਬੀ ਵਿੱਚ ਬੋਲਾਂਗੀ। ਮੈਂ ਤੁਹਾਡੀ ਕਿਵੇਂ ਮਦਦ ਕਰ ਸਕਦੀ ਹਾਂ?",
                'ta-IN': "நான் இப்போது தமிழில் பேசுவேன். நான் உங்களுக்கு எப்படி உதவ முடியும்?",
                'te-IN': "నేను ఇప్పుడు తెలుగులో మాట్లాడతాను. నేను మీకు ఎలా సహాయం చేయగలను?"
            }

            confirmation_text = confirmations.get(new_language, confirmations['en-IN'])

            logger.info(f"🌐 Sending language switch confirmation: {new_language}")

            # Get appropriate speaker
            speaker = self._get_speaker_for_language(new_language)

            # Generate confirmation audio
            confirmation_audio = await sarvam_service.text_to_speech(
                text=confirmation_text,
                language=new_language,
                speaker=speaker
            )

            if confirmation_audio:
                confirmation_message = {
                    "type": "audio",
                    "audio_b64": confirmation_audio,
                    "chunk_id": self.chunk_counter
                }

                self.chunk_counter += 1

                await websocket.send_text(json.dumps(confirmation_message))
                logger.info(f"✅ Sent language switch confirmation to {connection_id}")

                # Update call state
                if connection_id in self.call_states:
                    self.call_states[connection_id]['last_ai_response'] = datetime.now()
                    self.call_states[connection_id]['waiting_for_user'] = True

        except Exception as e:
            logger.error(f"Failed to send language switch confirmation: {e}")

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

    def _get_knowledge_base_for_call(self, call_id: str, stream_id: str = None, account_id: str = None) -> Optional[str]:
        """Look up knowledge base ID associated with a call using multiple possible identifiers"""
        try:
            from fastapi_app import call_history
            logger.info(f"🔍 Looking up knowledge base for call_id: '{call_id}', stream_id: '{stream_id}', account_id: '{account_id}'")
            logger.info(f"📚 Call history has {len(call_history)} entries")

            if not call_id and not stream_id:
                logger.warning(f"⚠️ No identifiers provided for lookup")
                return None

            # Try to find the most recent call with a knowledge base (for Teler calls)
            # Since Teler uses different IDs, we'll use a time-based approach
            # Look for calls initiated in the last 5 minutes with a knowledge base
            from datetime import datetime, timedelta
            recent_threshold = datetime.now() - timedelta(minutes=5)

            for idx, call in enumerate(call_history):
                stored_call_id = call.get('call_id')
                kb_id = call.get('knowledge_base_id')
                call_timestamp = call.get('timestamp')
                call_type = call.get('call_type')

                logger.info(f"  [{idx}] call_id: '{stored_call_id}' | KB: '{kb_id}' | Type: '{call_type}' | Time: {call_timestamp}")

                # Direct match on call_id
                if stored_call_id == call_id:
                    if kb_id:
                        logger.info(f"✅ Found knowledge base '{kb_id}' for call '{call_id}' (direct match)")
                        return kb_id
                    else:
                        logger.info(f"ℹ️ Call '{call_id}' found but no knowledge base associated")
                        return None

            # If no direct match, find the most recent "conversation" type call with a KB
            logger.info(f"🔍 No direct match found, looking for recent conversation calls with KB...")
            for idx, call in enumerate(call_history):
                call_type = call.get('call_type')
                kb_id = call.get('knowledge_base_id')
                call_timestamp_str = call.get('timestamp')

                if call_type == 'conversation' and kb_id:
                    try:
                        call_time = datetime.fromisoformat(call_timestamp_str)
                        if call_time >= recent_threshold:
                            logger.info(f"✅ Using knowledge base '{kb_id}' from recent call (within 5 min): {call.get('call_id')}")
                            return kb_id
                    except:
                        pass

            logger.warning(f"❌ No matching call found in history for call_id: '{call_id}'")
            logger.warning(f"Available call IDs: {[call.get('call_id') for call in call_history]}")
            return None
        except Exception as e:
            logger.error(f"❌ Error looking up knowledge base for call: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None

# Global instance
websocket_handler = TelerWebSocketHandler()