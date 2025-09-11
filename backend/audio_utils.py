#!/usr/bin/env python3
"""
Audio utilities for Teler WebSocket streaming
Handles audio format conversion and processing
"""

import base64
import logging
from typing import Dict, Any, Optional
import io
import wave

logger = logging.getLogger(__name__)

def convert_teler_to_sarvam_audio(audio_b64: str) -> str:
    """
    Convert Teler audio format to Sarvam TTS format
    
    Args:
        audio_b64: Base64 encoded audio from Teler
        
    Returns:
        Base64 encoded audio in Sarvam format
    """
    try:
        # Decode the base64 audio
        audio_data = base64.b64decode(audio_b64)
        
        # For now, return as-is since we don't have specific format requirements
        # In a real implementation, you would convert between audio formats
        return audio_b64
        
    except Exception as e:
        logger.error(f"Error converting Teler to Sarvam audio: {e}")
        return audio_b64

def convert_sarvam_to_teler_audio(audio_b64: str) -> str:
    """
    Convert Sarvam TTS audio format to Teler format
    
    Args:
        audio_b64: Base64 encoded audio from Sarvam TTS
        
    Returns:
        Base64 encoded audio in Teler format
    """
    try:
        # Decode the base64 audio
        audio_data = base64.b64decode(audio_b64)
        
        # For now, return as-is since we don't have specific format requirements
        # In a real implementation, you would convert between audio formats
        return audio_b64
        
    except Exception as e:
        logger.error(f"Error converting Sarvam to Teler audio: {e}")
        return audio_b64

def create_silence_audio(duration_ms: int = 1000, sample_rate: int = 8000) -> str:
    """
    Create silence audio in base64 format
    
    Args:
        duration_ms: Duration in milliseconds
        sample_rate: Sample rate in Hz
        
    Returns:
        Base64 encoded silence audio
    """
    try:
        # Calculate number of samples
        samples = int(duration_ms * sample_rate / 1000)
        
        # Create silence (zeros)
        silence_data = b'\x00' * (samples * 2)  # 16-bit audio = 2 bytes per sample
        
        # Create WAV file in memory
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, 'wb') as wav_file:
            wav_file.setnchannels(1)  # Mono
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(silence_data)
        
        # Get WAV data and encode to base64
        wav_data = wav_buffer.getvalue()
        return base64.b64encode(wav_data).decode('utf-8')
        
    except Exception as e:
        logger.error(f"Error creating silence audio: {e}")
        # Return minimal WAV header as fallback
        return "UklGRiQAAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQAAAAA="

def validate_audio_format(audio_b64: str) -> bool:
    """
    Validate if the base64 string contains valid audio data
    
    Args:
        audio_b64: Base64 encoded audio data
        
    Returns:
        True if valid, False otherwise
    """
    try:
        # Try to decode base64
        audio_data = base64.b64decode(audio_b64)
        
        # Check if it has minimum length
        if len(audio_data) < 44:  # Minimum WAV header size
            return False
            
        # Check for WAV header
        if audio_data[:4] == b'RIFF' and audio_data[8:12] == b'WAVE':
            return True
            
        # For other formats, just check if it's not empty
        return len(audio_data) > 0
        
    except Exception as e:
        logger.error(f"Error validating audio format: {e}")
        return False

def get_audio_duration(audio_b64: str) -> Optional[float]:
    """
    Get duration of audio in seconds
    
    Args:
        audio_b64: Base64 encoded audio data
        
    Returns:
        Duration in seconds, or None if unable to determine
    """
    try:
        audio_data = base64.b64decode(audio_b64)
        
        # Try to parse as WAV
        if audio_data[:4] == b'RIFF' and audio_data[8:12] == b'WAVE':
            # Parse WAV header to get duration
            # This is a simplified parser
            sample_rate = int.from_bytes(audio_data[24:28], 'little')
            data_size = int.from_bytes(audio_data[40:44], 'little')
            bytes_per_sample = 2  # Assuming 16-bit
            channels = int.from_bytes(audio_data[22:24], 'little')
            
            duration = data_size / (sample_rate * bytes_per_sample * channels)
            return duration
            
        return None
        
    except Exception as e:
        logger.error(f"Error getting audio duration: {e}")
        return None

def resample_audio(audio_b64: str, target_sample_rate: int = 8000) -> str:
    """
    Resample audio to target sample rate
    
    Args:
        audio_b64: Base64 encoded audio data
        target_sample_rate: Target sample rate in Hz
        
    Returns:
        Base64 encoded resampled audio
    """
    try:
        # For now, return as-is since we don't have audio processing libraries
        # In a real implementation, you would use libraries like librosa or pydub
        logger.info(f"Resampling audio to {target_sample_rate}Hz (placeholder)")
        return audio_b64
        
    except Exception as e:
        logger.error(f"Error resampling audio: {e}")
        return audio_b64

def get_audio_info(audio_b64: str) -> Dict[str, Any]:
    """
    Get information about audio data
    
    Args:
        audio_b64: Base64 encoded audio data
        
    Returns:
        Dictionary with audio information
    """
    try:
        audio_data = base64.b64decode(audio_b64)
        
        info = {
            'size_bytes': len(audio_data),
            'format': 'unknown',
            'duration': None,
            'sample_rate': None,
            'channels': None,
            'valid': False
        }
        
        # Check if it's WAV format
        if len(audio_data) >= 44 and audio_data[:4] == b'RIFF' and audio_data[8:12] == b'WAVE':
            info['format'] = 'wav'
            info['valid'] = True
            
            try:
                info['sample_rate'] = int.from_bytes(audio_data[24:28], 'little')
                info['channels'] = int.from_bytes(audio_data[22:24], 'little')
                data_size = int.from_bytes(audio_data[40:44], 'little')
                bytes_per_sample = 2  # Assuming 16-bit
                
                if info['sample_rate'] and info['channels']:
                    info['duration'] = data_size / (info['sample_rate'] * bytes_per_sample * info['channels'])
            except:
                pass
        
        return info
        
    except Exception as e:
        logger.error(f"Error getting audio info: {e}")
        return {
            'size_bytes': 0,
            'format': 'error',
            'duration': None,
            'sample_rate': None,
            'channels': None,
            'valid': False
        }