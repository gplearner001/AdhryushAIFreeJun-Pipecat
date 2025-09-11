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
    
    async def speech_to_text(self, audio_base64: str, language: str = "hi-IN") -> Optional[str]:
        """
        Convert speech to text using Sarvam AI STT API.
        
        Args:
            audio_base64: Base64 encoded audio data
            language: Language code (default: hi-IN for Hindi)
            
        Returns:
            Transcribed text or None if failed
        """
        if not self.is_available():
            logger.warning("Sarvam AI not available for STT")
            return None
        
        try:
            logger.info(f"Converting speech to text using Sarvam AI (language: {language})")
            
            # Prepare the request payload
            payload = {
                "language_code": language,
                "model": "saaras:v1",
                "file": audio_base64
            }
            
            headers = {
                "API-Subscription-Key": self.api_key,
                "Content-Type": "application/json"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/speech-to-text",
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    
                    if response.status == 200:
                        result = await response.json()
                        transcript = result.get("transcript", "")
                        logger.info(f"STT successful: '{transcript}'")
                        return transcript
                    else:
                        error_text = await response.text()
                        logger.error(f"Sarvam STT API error {response.status}: {error_text}")
                        return None
                        
        except asyncio.TimeoutError:
            logger.error("Sarvam STT API timeout")
            return None
        except Exception as e:
            logger.error(f"Error in Sarvam STT: {str(e)}")
            return None
    
    async def text_to_speech(self, text: str, language: str = "hi-IN", speaker: str = "meera") -> Optional[str]:
        """
        Convert text to speech using Sarvam AI TTS API.
        
        Args:
            text: Text to convert to speech
            language: Language code (default: hi-IN for Hindi)
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
    
    async def detect_language(self, audio_base64: str) -> Optional[str]:
        """
        Detect language from audio using Sarvam AI.
        
        Args:
            audio_base64: Base64 encoded audio data
            
        Returns:
            Detected language code or None if failed
        """
        if not self.is_available():
            return "hi-IN"  # Default to Hindi
        
        try:
            # For now, return default language
            # You can implement language detection if Sarvam AI supports it
            return "hi-IN"
            
        except Exception as e:
            logger.error(f"Error in language detection: {str(e)}")
            return "hi-IN"

# Global instance
sarvam_service = SarvamAIService()