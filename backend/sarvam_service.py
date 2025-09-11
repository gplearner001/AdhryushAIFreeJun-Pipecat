#!/usr/bin/env python3
"""
Sarvam AI Service for Speech-to-Text and Text-to-Speech
Integrates with Sarvam AI's streaming APIs for real-time audio processing
"""

import os
import logging
import asyncio
import base64
from typing import Dict, Any, Optional, AsyncGenerator
from datetime import datetime

try:
    from sarvamai import AsyncSarvamAI, AudioOutput
    SARVAM_AVAILABLE = True
except ImportError:
    SARVAM_AVAILABLE = False
    AsyncSarvamAI = None
    AudioOutput = None

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

class SarvamAIService:
    """Service for Sarvam AI Speech-to-Text and Text-to-Speech operations"""
    
    def __init__(self):
        self.api_key = os.getenv('SARVAM_API_KEY')
        if not self.api_key or not SARVAM_AVAILABLE:
            if not self.api_key:
                logger.warning("SARVAM_API_KEY not found, Sarvam AI features will be disabled")
            if not SARVAM_AVAILABLE:
                logger.warning("sarvamai library not available, Sarvam AI features will be disabled")
            self.client = None
        else:
            try:
                self.client = AsyncSarvamAI(api_subscription_key=self.api_key)
                logger.info("Sarvam AI service initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize Sarvam AI service: {str(e)}")
                self.client = None
    
    def is_available(self) -> bool:
        """Check if Sarvam AI service is available"""
        return self.client is not None and SARVAM_AVAILABLE and self.api_key is not None
    
    async def transcribe_audio_stream(
        self, 
        audio_b64: str, 
        language_code: str = "en-IN",
        sample_rate: int = 16000,
        encoding: str = "audio/wav",
        use_vad_signals: bool = True
    ) -> Optional[str]:
        """
        Transcribe audio using Sarvam AI's streaming STT
        
        Args:
            audio_b64: Base64 encoded audio data
            language_code: Language for transcription (e.g., "en-IN", "hi-IN")
            sample_rate: Audio sample rate in Hz
            encoding: Audio encoding format
            use_vad_signals: Enable VAD signals for better transcription
            
        Returns:
            Transcribed text or None if failed
        """
        if not self.is_available():
            logger.warning("Sarvam AI service not available for transcription")
            return None
        
        try:
            logger.debug(f"Starting STT transcription for {len(audio_b64)} bytes of audio")
            
            async with self.client.speech_to_text_streaming.connect(
                language_code=language_code,
                model="saarika:v2.5",
                high_vad_sensitivity=True,
                vad_signals=use_vad_signals,
                sample_rate=sample_rate,
                input_audio_codec="wav"
            ) as ws:
                # Send audio data
                await ws.transcribe(
                    audio=audio_b64,
                    encoding=encoding,
                    sample_rate=sample_rate
                )
                
                logger.debug("Audio sent to Sarvam STT")
                
                # Handle responses with VAD signals
                transcript_text = ""
                if use_vad_signals:
                    # Wait for the complete sequence: speech_start -> speech_end -> transcript
                    try:
                        async with asyncio.timeout(10):  # 10 second timeout
                            async for message in ws:
                                logger.debug(f"STT Response: {message}")
                                
                                if hasattr(message, 'type'):
                                    if message.type == "transcript" and hasattr(message, 'text'):
                                        transcript_text = message.text
                                        break
                                elif isinstance(message, dict):
                                    if message.get('type') == 'transcript':
                                        transcript_text = message.get('text', '')
                                        break
                                    elif 'text' in message:
                                        transcript_text = message['text']
                                        break
                    except asyncio.TimeoutError:
                        logger.warning("STT transcription timeout")
                else:
                    # Simple response without VAD signals
                    response = await ws.recv()
                    logger.debug(f"STT Response: {response}")
                    
                    if hasattr(response, 'text'):
                        transcript_text = response.text
                    elif isinstance(response, dict) and 'text' in response:
                        transcript_text = response['text']
                
                if transcript_text:
                    logger.info(f"Transcription successful: {transcript_text[:100]}...")
                    return transcript_text.strip()
                else:
                    logger.warning("No transcript text received from Sarvam STT")
                    return None
                    
        except Exception as e:
            logger.error(f"Error in Sarvam STT transcription: {str(e)}")
            return None
    
    async def translate_audio_stream(
        self, 
        audio_b64: str,
        sample_rate: int = 16000,
        encoding: str = "audio/wav",
        use_vad_signals: bool = True
    ) -> Optional[Dict[str, str]]:
        """
        Transcribe and translate audio using Sarvam AI's streaming STT Translation
        
        Args:
            audio_b64: Base64 encoded audio data
            sample_rate: Audio sample rate in Hz
            encoding: Audio encoding format
            use_vad_signals: Enable VAD signals for better processing
            
        Returns:
            Dictionary with 'transcript' and 'translation' or None if failed
        """
        if not self.is_available():
            logger.warning("Sarvam AI service not available for translation")
            return None
        
        try:
            logger.debug(f"Starting STT translation for {len(audio_b64)} bytes of audio")
            
            async with self.client.speech_to_text_translate_streaming.connect(
                model="saaras:v2.5",
                high_vad_sensitivity=True,
                vad_signals=use_vad_signals,
                sample_rate=sample_rate
            ) as ws:
                # Send audio data
                await ws.translate(
                    audio=audio_b64,
                    encoding=encoding,
                    sample_rate=sample_rate
                )
                
                logger.debug("Audio sent to Sarvam STT Translation")
                
                # Handle responses with VAD signals
                result = {}
                if use_vad_signals:
                    try:
                        async with asyncio.timeout(10):  # 10 second timeout
                            async for message in ws:
                                logger.debug(f"STT Translation Response: {message}")
                                
                                if isinstance(message, dict):
                                    if message.get('type') == 'translation':
                                        result['translation'] = message.get('text', '')
                                        result['transcript'] = message.get('original_text', '')
                                        break
                                    elif 'text' in message:
                                        result['translation'] = message['text']
                                        break
                    except asyncio.TimeoutError:
                        logger.warning("STT translation timeout")
                else:
                    # Simple response without VAD signals
                    response = await ws.recv()
                    logger.debug(f"STT Translation Response: {response}")
                    
                    if isinstance(response, dict):
                        result['translation'] = response.get('text', '')
                        result['transcript'] = response.get('original_text', '')
                
                if result.get('translation'):
                    logger.info(f"Translation successful: {result['translation'][:100]}...")
                    return result
                else:
                    logger.warning("No translation received from Sarvam STT Translation")
                    return None
                    
        except Exception as e:
            logger.error(f"Error in Sarvam STT translation: {str(e)}")
            return None
    
    async def generate_speech_stream(
        self, 
        text: str,
        language_code: str = "en-IN",
        speaker: str = "anushka",
        output_codec: str = "wav",
        output_bitrate: str = "128k"
    ) -> AsyncGenerator[bytes, None]:
        """
        Generate speech from text using Sarvam AI's streaming TTS
        
        Args:
            text: Text to convert to speech
            language_code: Target language code (e.g., "en-IN", "hi-IN")
            speaker: Voice speaker name
            output_codec: Output audio codec (wav, mp3, etc.)
            output_bitrate: Audio bitrate
            
        Yields:
            Audio chunks as bytes
        """
        if not self.is_available():
            logger.warning("Sarvam AI service not available for TTS")
            return
        
        try:
            logger.debug(f"Starting TTS generation for text: {text[:100]}...")
            
            async with self.client.text_to_speech_streaming.connect(
                model="bulbul:v2",
                send_completion_event=True
            ) as ws:
                # Configure TTS settings
                await ws.configure(
                    target_language_code=language_code,
                    speaker=speaker,
                    output_audio_codec=output_codec,
                    output_audio_bitrate=output_bitrate,
                    min_buffer_size=50,
                    max_chunk_length=200
                )
                
                logger.debug("TTS configuration sent")
                
                # Send text for conversion
                await ws.convert(text)
                logger.debug("Text sent for TTS conversion")
                
                # Flush to ensure processing
                await ws.flush()
                logger.debug("TTS buffer flushed")
                
                # Receive audio chunks
                chunk_count = 0
                async for message in ws:
                    if isinstance(message, AudioOutput):
                        chunk_count += 1
                        audio_chunk = base64.b64decode(message.data.audio)
                        logger.debug(f"Received TTS audio chunk {chunk_count}, size: {len(audio_chunk)} bytes")
                        yield audio_chunk
                    elif isinstance(message, dict) and message.get('type') == 'audio':
                        chunk_count += 1
                        audio_chunk = base64.b64decode(message['data']['audio'])
                        logger.debug(f"Received TTS audio chunk {chunk_count}, size: {len(audio_chunk)} bytes")
                        yield audio_chunk
                
                logger.info(f"TTS generation completed with {chunk_count} chunks")
                
        except Exception as e:
            logger.error(f"Error in Sarvam TTS generation: {str(e)}")
    
    async def generate_speech_base64(
        self, 
        text: str,
        language_code: str = "en-IN",
        speaker: str = "anushka",
        output_codec: str = "wav"
    ) -> Optional[str]:
        """
        Generate speech and return as base64 encoded string
        
        Args:
            text: Text to convert to speech
            language_code: Target language code
            speaker: Voice speaker name
            output_codec: Output audio codec
            
        Returns:
            Base64 encoded audio data or None if failed
        """
        try:
            audio_chunks = []
            async for chunk in self.generate_speech_stream(
                text=text,
                language_code=language_code,
                speaker=speaker,
                output_codec=output_codec
            ):
                audio_chunks.append(chunk)
            
            if audio_chunks:
                # Combine all chunks
                combined_audio = b''.join(audio_chunks)
                # Encode to base64
                audio_b64 = base64.b64encode(combined_audio).decode('utf-8')
                logger.info(f"Generated {len(combined_audio)} bytes of audio, base64 length: {len(audio_b64)}")
                return audio_b64
            else:
                logger.warning("No audio chunks generated")
                return None
                
        except Exception as e:
            logger.error(f"Error generating speech base64: {str(e)}")
            return None
    
    def get_supported_languages(self) -> Dict[str, str]:
        """Get supported language codes and names"""
        return {
            "en-IN": "English (India)",
            "hi-IN": "Hindi (India)",
            "kn-IN": "Kannada (India)",
            "ta-IN": "Tamil (India)",
            "te-IN": "Telugu (India)",
            "ml-IN": "Malayalam (India)",
            "bn-IN": "Bengali (India)",
            "gu-IN": "Gujarati (India)",
            "mr-IN": "Marathi (India)",
            "pa-IN": "Punjabi (India)"
        }
    
    def get_supported_speakers(self) -> list:
        """Get supported TTS speaker names"""
        return ["anushka", "meera", "arjun", "kavya", "ravi"]

# Global instance
sarvam_service = SarvamAIService()