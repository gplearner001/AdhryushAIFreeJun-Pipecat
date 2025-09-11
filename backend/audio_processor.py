#!/usr/bin/env python3
"""
Audio processing service for speech-to-text and text-to-speech conversion
Handles audio conversion between base64, WAV, and text formats
"""

import base64
import io
import wave
import logging
import asyncio
from typing import Optional, Tuple
import tempfile
import os

try:
    import speech_recognition as sr
    import pyttsx3
    STT_TTS_AVAILABLE = True
except ImportError:
    STT_TTS_AVAILABLE = False
    sr = None
    pyttsx3 = None

logger = logging.getLogger(__name__)

class AudioProcessor:
    """Handles audio processing for STT and TTS operations"""
    
    def __init__(self):
        self.recognizer = None
        self.tts_engine = None
        
        if STT_TTS_AVAILABLE:
            try:
                # Initialize speech recognition
                self.recognizer = sr.Recognizer()
                self.recognizer.energy_threshold = 300
                self.recognizer.dynamic_energy_threshold = True
                
                # Initialize TTS engine
                self.tts_engine = pyttsx3.init()
                self.tts_engine.setProperty('rate', 150)  # Speed of speech
                self.tts_engine.setProperty('volume', 0.9)  # Volume level
                
                logger.info("Audio processor initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize audio processor: {e}")
                self.recognizer = None
                self.tts_engine = None
        else:
            logger.warning("Speech recognition and TTS libraries not available")
    
    def is_available(self) -> bool:
        """Check if audio processing is available"""
        return self.recognizer is not None and self.tts_engine is not None
    
    async def base64_to_text(self, audio_b64: str, encoding: str = "audio/l16", sample_rate: int = 8000) -> Optional[str]:
        """
        Convert base64 encoded audio to text using speech recognition
        
        Args:
            audio_b64: Base64 encoded audio data
            encoding: Audio encoding format
            sample_rate: Audio sample rate
            
        Returns:
            Transcribed text or None if conversion fails
        """
        if not self.is_available():
            logger.warning("Audio processor not available for STT")
            return None
        
        try:
            # Decode base64 audio
            audio_data = base64.b64decode(audio_b64)
            
            # Convert to WAV format for speech recognition
            wav_data = await self._convert_to_wav(audio_data, encoding, sample_rate)
            
            if not wav_data:
                return None
            
            # Create audio source from WAV data
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                temp_file.write(wav_data)
                temp_file.flush()
                
                try:
                    # Use speech recognition
                    with sr.AudioFile(temp_file.name) as source:
                        # Adjust for ambient noise
                        self.recognizer.adjust_for_ambient_noise(source, duration=0.2)
                        audio = self.recognizer.record(source)
                    
                    # Recognize speech using Google Speech Recognition
                    text = self.recognizer.recognize_google(audio)
                    logger.info(f"STT conversion successful: '{text}'")
                    return text
                    
                except sr.UnknownValueError:
                    logger.debug("Speech recognition could not understand audio")
                    return None
                except sr.RequestError as e:
                    logger.error(f"Speech recognition service error: {e}")
                    return None
                finally:
                    # Clean up temp file
                    try:
                        os.unlink(temp_file.name)
                    except:
                        pass
                        
        except Exception as e:
            logger.error(f"Error in base64_to_text conversion: {e}")
            return None
    
    async def text_to_base64(self, text: str, encoding: str = "audio/l16", sample_rate: int = 8000) -> Optional[str]:
        """
        Convert text to base64 encoded audio using text-to-speech
        
        Args:
            text: Text to convert to speech
            encoding: Target audio encoding format
            sample_rate: Target audio sample rate
            
        Returns:
            Base64 encoded audio data or None if conversion fails
        """
        if not self.is_available():
            logger.warning("Audio processor not available for TTS")
            return None
        
        try:
            # Generate speech audio
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                # Save TTS output to temporary file
                self.tts_engine.save_to_file(text, temp_file.name)
                self.tts_engine.runAndWait()
                
                try:
                    # Read the generated audio file
                    with open(temp_file.name, 'rb') as audio_file:
                        audio_data = audio_file.read()
                    
                    # Convert to target format if needed
                    converted_audio = await self._convert_audio_format(audio_data, encoding, sample_rate)
                    
                    if converted_audio:
                        # Encode to base64
                        audio_b64 = base64.b64encode(converted_audio).decode('utf-8')
                        logger.info(f"TTS conversion successful for text: '{text[:50]}...'")
                        return audio_b64
                    
                except Exception as e:
                    logger.error(f"Error reading TTS output: {e}")
                    return None
                finally:
                    # Clean up temp file
                    try:
                        os.unlink(temp_file.name)
                    except:
                        pass
                        
        except Exception as e:
            logger.error(f"Error in text_to_base64 conversion: {e}")
            return None
    
    async def _convert_to_wav(self, audio_data: bytes, encoding: str, sample_rate: int) -> Optional[bytes]:
        """
        Convert audio data to WAV format
        
        Args:
            audio_data: Raw audio data
            encoding: Source audio encoding
            sample_rate: Audio sample rate
            
        Returns:
            WAV formatted audio data
        """
        try:
            if encoding == "audio/l16":
                # Linear PCM 16-bit format
                # Create WAV file in memory
                wav_buffer = io.BytesIO()
                
                with wave.open(wav_buffer, 'wb') as wav_file:
                    wav_file.setnchannels(1)  # Mono
                    wav_file.setsampwidth(2)  # 16-bit
                    wav_file.setframerate(sample_rate)
                    wav_file.writeframes(audio_data)
                
                wav_buffer.seek(0)
                return wav_buffer.read()
            else:
                logger.warning(f"Unsupported audio encoding: {encoding}")
                return None
                
        except Exception as e:
            logger.error(f"Error converting to WAV: {e}")
            return None
    
    async def _convert_audio_format(self, audio_data: bytes, target_encoding: str, target_sample_rate: int) -> Optional[bytes]:
        """
        Convert audio to target format
        
        Args:
            audio_data: Source audio data (WAV format)
            target_encoding: Target encoding format
            target_sample_rate: Target sample rate
            
        Returns:
            Converted audio data
        """
        try:
            if target_encoding == "audio/l16":
                # Read WAV file and extract raw PCM data
                wav_buffer = io.BytesIO(audio_data)
                
                with wave.open(wav_buffer, 'rb') as wav_file:
                    # Check if conversion is needed
                    if wav_file.getframerate() == target_sample_rate and wav_file.getsampwidth() == 2:
                        # Already in correct format, return raw frames
                        return wav_file.readframes(wav_file.getnframes())
                    else:
                        # Simple conversion (may need more sophisticated resampling)
                        frames = wav_file.readframes(wav_file.getnframes())
                        return frames
            else:
                logger.warning(f"Unsupported target encoding: {target_encoding}")
                return None
                
        except Exception as e:
            logger.error(f"Error converting audio format: {e}")
            return None

# Global instance
audio_processor = AudioProcessor()