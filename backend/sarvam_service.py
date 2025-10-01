#!/usr/bin/env python3
"""
Sarvam AI Service for Speech-to-Text and Text-to-Speech
Integrates with Sarvam AI API for audio processing in calls
"""

import os
import base64
import logging
import aiohttp
import asyncio
import tempfile
import io
import struct
import wave
from typing import Optional, Dict, Any
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

class SarvamAIService:
    """Service for interacting with Sarvam AI API for STT and TTS."""
    
    def __init__(self):
        self.api_key = os.getenv('SARVAM_API_KEY')
        self.base_url = "https://api.sarvam.ai"
        
        if not self.api_key:
            logger.warning("SARVAM_API_KEY not found, Sarvam AI features will be disabled")
        else:
            logger.info("Sarvam AI service initialized successfully")
    
    def is_available(self) -> bool:
        """Check if Sarvam AI service is available."""
        return self.api_key is not None
    
    async def speech_to_text(self, audio_base64: str, language: str = "en-IN") -> Optional[Dict[str, Any]]:
        """
        Convert speech to text using Sarvam AI STT API.

        Args:
            audio_base64: Base64 encoded audio data
            language: Language code (default: en-IN for Hindi)

        Returns:
            Dictionary with 'transcript' and 'language' keys, or None if failed
        """
        if not self.is_available():
            logger.warning("Sarvam AI not available for STT")
            return None
        
        try:
            logger.info(f"Converting speech to text using Sarvam AI (language: {language})")
            
            # Decode base64 audio data (raw PCM from Teler)
            audio_data = base64.b64decode(audio_base64)
            logger.info(f"Decoded raw audio data: {len(audio_data)} bytes")
            
            # Convert raw PCM to WAV format
            wav_data = self._convert_raw_pcm_to_wav(audio_data)
            if not wav_data:
                logger.error("Failed to convert raw PCM to WAV format")
                return None
            
            # Create temporary WAV file
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                temp_file.write(wav_data)
                temp_file_path = temp_file.name
            
            logger.info(f"Temporary WAV file created at: {temp_file_path}")
            
            # Prepare multipart form data
            data = aiohttp.FormData()
            data.add_field('language_code', language)
            data.add_field('model', 'saarika:v2.5')
            
            # Add the MP3 file
            with open(temp_file_path, 'rb') as f:
                data.add_field('file', f, filename='audio.wav', content_type='audio/wav')
                
                headers = {
                    "API-Subscription-Key": self.api_key
                }
                
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        f"{self.base_url}/speech-to-text",
                        data=data,
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=30)
                    ) as response:
                        
                        if response.status == 200:
                            result = await response.json()
                            transcript = result.get("transcript", "")
                            logger.info(f"STT successful: '{transcript}' (language: {language})")
                            return {
                                "transcript": transcript,
                                "language": language
                            }
                        else:
                            error_text = await response.text()
                            logger.error(f"Sarvam STT API error {response.status}: {error_text}")
                            return None
            
        except Exception as e:
            logger.error(f"Error in Sarvam STT: {str(e)}")
            return None
        finally:
            # Clean up temporary file
            try:
                if 'temp_file_path' in locals():
                    os.unlink(temp_file_path)
            except Exception as e:
                logger.warning(f"Failed to clean up temp file: {e}")
                        
    def _convert_raw_pcm_to_wav(self, raw_audio_data: bytes, sample_rate: int = 8000, channels: int = 1, sample_width: int = 2) -> Optional[bytes]:
        """
        Convert raw PCM audio data to WAV format.
        
        Args:
            raw_audio_data: Raw PCM audio bytes from Teler
            sample_rate: Sample rate in Hz (default: 8000 for Teler)
            channels: Number of audio channels (default: 1 for mono)
            sample_width: Sample width in bytes (default: 2 for 16-bit)
            
        Returns:
            WAV formatted audio data as bytes
        """
        try:
            logger.info(f"Converting raw PCM to WAV: {len(raw_audio_data)} bytes, {sample_rate}Hz, {channels} channel(s), {sample_width*8}-bit")
            
            # Validate input data
            if len(raw_audio_data) == 0:
                logger.error("Empty audio data provided")
                return None
            
            # Ensure data length is aligned to sample width
            expected_alignment = sample_width * channels
            if len(raw_audio_data) % expected_alignment != 0:
                # Pad with zeros to align
                padding_needed = expected_alignment - (len(raw_audio_data) % expected_alignment)
                raw_audio_data += b'\x00' * padding_needed
                logger.info(f"Padded audio data with {padding_needed} bytes for alignment")
            
            # Create WAV file in memory
            wav_buffer = io.BytesIO()
            
            with wave.open(wav_buffer, 'wb') as wav_file:
                wav_file.setnchannels(channels)
                wav_file.setsampwidth(sample_width)
                wav_file.setframerate(sample_rate)
                wav_file.writeframes(raw_audio_data)
            
            # Get WAV data
            wav_data = wav_buffer.getvalue()
            logger.info(f"Successfully converted to WAV: {len(wav_data)} bytes")
            
            return wav_data
            
        except Exception as e:
            logger.error(f"Error converting raw PCM to WAV: {str(e)}")
            return None
    
    def _save_debug_audio_files(self, raw_audio_data: bytes, wav_data: bytes, prefix: str = "debug"):
        """
        Save audio files for debugging purposes.
        
        Args:
            raw_audio_data: Raw PCM audio data
            wav_data: WAV formatted audio data
            prefix: Filename prefix
        """
        try:
            import time
            timestamp = int(time.time())
            
            # Save raw file
            raw_filename = f"/tmp/{prefix}_{timestamp}.raw"
            with open(raw_filename, 'wb') as f:
                f.write(raw_audio_data)
            logger.info(f"Saved raw audio to: {raw_filename}")
            
            # Save WAV file
            wav_filename = f"/tmp/{prefix}_{timestamp}.wav"
            with open(wav_filename, 'wb') as f:
                f.write(wav_data)
            logger.info(f"Saved WAV audio to: {wav_filename}")
            
        except Exception as e:
            logger.warning(f"Failed to save debug audio files: {e}")
    
    async def text_to_speech(self, text: str, language: str = "en-IN", speaker: str = "meera") -> Optional[str]:
        """
        Convert text to speech using Sarvam AI TTS API.
        
        Args:
            text: Text to convert to speech
            language: Language code (default: en-IN for Hindi)
            speaker: Speaker voice (default: meera)
            
        Returns:
            Base64 encoded audio data or None if failed
        """
        if not self.is_available():
            logger.warning("Sarvam AI not available for TTS")
            return None
        
        try:
            logger.info(f"Converting text to speech using Sarvam AI: '{text}' (language: {language}, speaker: {speaker})")
            
            # Prepare the request payload
            payload = {
                "inputs": [text],
                "target_language_code": language,
                "speaker": speaker,
                "pitch": 0,
                "pace": 1.0,
                "loudness": 1.0,
                "speech_sample_rate": 8000,
                "enable_preprocessing": True,
                "model": "bulbul:v1"
            }
            
            headers = {
                "API-Subscription-Key": self.api_key,
                "Content-Type": "application/json"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/text-to-speech",
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    
                    if response.status == 200:
                        result = await response.json()
                        audio_base64 = result.get("audios", [None])[0]
                        if audio_base64:
                            logger.info(f"TTS successful for text: '{text}'")
                            return audio_base64
                        else:
                            logger.error("No audio data in Sarvam TTS response")
                            return None
                    else:
                        error_text = await response.text()
                        logger.error(f"Sarvam TTS API error {response.status}: {error_text}")
                        return None
                        
        except asyncio.TimeoutError:
            logger.error("Sarvam TTS API timeout")
            return None
        except Exception as e:
            logger.error(f"Error in Sarvam TTS: {str(e)}")
            return None
    
    async def detect_language_from_text(self, text: str) -> Optional[str]:
        """
        Detect language from text using Sarvam AI Language Identification API.

        Args:
            text: Text to detect language from

        Returns:
            Detected language code (e.g., 'en-IN', 'hi-IN') or None if failed
        """
        if not self.is_available():
            return "en-IN"  # Default to English-India

        try:
            logger.info(f"Detecting language from text: '{text[:50]}...'")

            payload = {
                "input": text
            }

            headers = {
                "API-Subscription-Key": self.api_key,
                "Content-Type": "application/json"
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/text-lid",
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:

                    if response.status == 200:
                        result = await response.json()
                        language_code = result.get("language_code")
                        script_code = result.get("script_code")

                        if language_code:
                            logger.info(f"Detected language: {language_code} (script: {script_code})")
                            return language_code
                        else:
                            logger.warning("No language code in response")
                            return "en-IN"
                    else:
                        error_text = await response.text()
                        logger.error(f"Language detection API error {response.status}: {error_text}")
                        return "en-IN"

        except Exception as e:
            logger.error(f"Error in language detection: {str(e)}")
            return "en-IN"

    def get_language_map(self) -> Dict[str, str]:
        """
        Get mapping of common language keywords to language codes.

        Returns:
            Dictionary mapping language keywords to Sarvam AI language codes
        """
        return {
            # English keywords
            "english": "en-IN",
            "hindi": "hi-IN",
            "bengali": "bn-IN",
            "gujarati": "gu-IN",
            "kannada": "kn-IN",
            "malayalam": "ml-IN",
            "marathi": "mr-IN",
            "odia": "or-IN",
            "punjabi": "pa-IN",
            "tamil": "ta-IN",
            "telugu": "te-IN",
            # Hindi keywords
            "अंग्रेजी": "en-IN",
            "हिंदी": "hi-IN",
            "बंगाली": "bn-IN",
            "गुजराती": "gu-IN",
            "कन्नड़": "kn-IN",
            "मलयालम": "ml-IN",
            "मराठी": "mr-IN",
            "उड़िया": "or-IN",
            "पंजाबी": "pa-IN",
            "तमिल": "ta-IN",
            "तेलुगु": "te-IN"
        }

    def detect_language_switch_request(self, text: str) -> Optional[str]:
        """
        Detect if user is requesting a language switch.

        Args:
            text: User's transcript

        Returns:
            Language code if switch detected, None otherwise
        """
        text_lower = text.lower().strip()

        # Common language switch patterns
        switch_patterns = [
            "switch to", "change to", "speak in", "talk in",
            "बदलो", "बोलो", "में बोलो"
        ]

        # Check if text contains switch pattern
        is_switch_request = any(pattern in text_lower for pattern in switch_patterns)

        if is_switch_request:
            # Look for language name in text
            language_map = self.get_language_map()

            for keyword, lang_code in language_map.items():
                if keyword in text_lower:
                    logger.info(f"Language switch detected: '{keyword}' -> {lang_code}")
                    return lang_code

        return None

# Global instance
sarvam_service = SarvamAIService()