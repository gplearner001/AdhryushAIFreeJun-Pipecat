#!/usr/bin/env python3
"""
Audio processor for handling speech-to-text and text-to-speech operations
Supports multiple STT providers and audio format conversions
"""

import os
import base64
import logging
import asyncio
import io
import wave
from typing import Optional, Dict, Any
from datetime import datetime

# Try to import speech recognition libraries
try:
    import speech_recognition as sr
    SPEECH_RECOGNITION_AVAILABLE = True
except ImportError:
    SPEECH_RECOGNITION_AVAILABLE = False
    sr = None

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    requests = None

logger = logging.getLogger(__name__)

class AudioProcessor:
    """Handles audio processing, STT, and TTS operations"""
    
    def __init__(self):
        self.google_api_key = os.getenv('GOOGLE_API_KEY')
        
        # Initialize speech recognizer if available
        if SPEECH_RECOGNITION_AVAILABLE:
            self.recognizer = sr.Recognizer()
            self.recognizer.energy_threshold = 300
            self.recognizer.dynamic_energy_threshold = True
            self.recognizer.pause_threshold = 0.8
            self.recognizer.phrase_threshold = 0.3
            logger.info("Speech recognition initialized")
        else:
            self.recognizer = None
            logger.warning("Speech recognition not available - install speech_recognition package")
        
        self.is_available = SPEECH_RECOGNITION_AVAILABLE
        logger.info(f"Audio processor available: {self.is_available}")
    
    def is_processor_available(self) -> bool:
        """Check if audio processor is available"""
        return self.is_available
    
    async def process_audio_chunk(self, audio_b64: str, connection_id: str) -> Optional[str]:
        """
        Process audio chunk and convert to text
        
        Args:
            audio_b64: Base64 encoded audio data
            connection_id: WebSocket connection ID
            
        Returns:
            Transcribed text or None if processing fails
        """
        if not self.is_available:
            logger.warning("Audio processor not available for STT")
            return None
        
        try:
            # Decode base64 audio
            audio_data = base64.b64decode(audio_b64)
            logger.debug(f"Processing audio chunk of {len(audio_data)} bytes for connection {connection_id}")
            
            # Convert audio to text
            text = await self._audio_to_text(audio_data)
            
            if text and text.strip():
                logger.info(f"STT Result for {connection_id}: '{text}'")
                return text.strip()
            else:
                logger.debug(f"No speech detected in audio chunk for {connection_id}")
                return None
                
        except Exception as e:
            logger.error(f"Error processing audio chunk: {e}")
            return None
    
    async def _audio_to_text(self, audio_data: bytes) -> Optional[str]:
        """Convert audio data to text using available STT services"""
        
        # Use Google Speech Recognition (free and reliable)
        if SPEECH_RECOGNITION_AVAILABLE:
            try:
                text = await self._google_stt(audio_data)
                if text:
                    return text
            except Exception as e:
                logger.error(f"Google STT failed: {e}")
        
        return None
    
    async def _google_stt(self, audio_data: bytes) -> Optional[str]:
        """Use Google Speech Recognition for speech-to-text"""
        try:
            # Convert raw audio to WAV format
            wav_data = self._convert_to_wav(audio_data)
            
            # Create AudioData object
            audio_source = sr.AudioData(wav_data, 8000, 2)  # 8kHz, 16-bit
            
            # Recognize speech using Google (free service)
            text = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.recognizer.recognize_google(audio_source)
            )
            
            logger.info(f"Google STT successful: '{text}'")
            return text
            
        except sr.UnknownValueError:
            logger.debug("Google STT could not understand audio")
            return None
        except sr.RequestError as e:
            logger.error(f"Google STT request error: {e}")
            return None
        except Exception as e:
            logger.error(f"Google STT error: {e}")
            return None
    
    def _convert_to_wav(self, audio_data: bytes, sample_rate: int = 8000, channels: int = 1) -> bytes:
        """
        Convert raw audio data to WAV format
        
        Args:
            audio_data: Raw audio bytes (assumed to be 16-bit PCM)
            sample_rate: Sample rate in Hz
            channels: Number of audio channels
            
        Returns:
            WAV formatted audio data
        """
        try:
            # Create WAV file in memory
            wav_buffer = io.BytesIO()
            
            with wave.open(wav_buffer, 'wb') as wav_file:
                wav_file.setnchannels(channels)
                wav_file.setsampwidth(2)  # 16-bit = 2 bytes
                wav_file.setframerate(sample_rate)
                wav_file.writeframes(audio_data)
            
            wav_buffer.seek(0)
            return wav_buffer.read()
            
        except Exception as e:
            logger.error(f"Error converting to WAV: {e}")
            # Return original data if conversion fails
            return audio_data
    
    async def text_to_speech(self, text: str) -> Optional[str]:
        """
        Convert text to speech and return base64 encoded audio
        
        Args:
            text: Text to convert to speech
            
        Returns:
            Base64 encoded audio data or None if TTS fails
        """
        if not text or not text.strip():
            return None
        
        # For now, we'll focus on STT. TTS can be added later with other providers
        logger.info(f"TTS requested for text: '{text}' - TTS not implemented yet")
        return None
    
    def get_status(self) -> Dict[str, Any]:
        """Get audio processor status"""
        return {
            "available": self.is_available,
            "speech_recognition": SPEECH_RECOGNITION_AVAILABLE,
            "google_stt": SPEECH_RECOGNITION_AVAILABLE,
            "primary_stt": "google" if SPEECH_RECOGNITION_AVAILABLE else "none",
            "services": {
                "stt": ["google"] if SPEECH_RECOGNITION_AVAILABLE else [],
                "tts": []  # TTS can be added later
            }
        }

# Global instance
audio_processor = AudioProcessor()