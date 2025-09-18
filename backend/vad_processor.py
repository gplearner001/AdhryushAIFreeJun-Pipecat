#!/usr/bin/env python3
"""
Voice Activity Detection (VAD) processor using WebRTC VAD
Detects speech in audio chunks before STT processing
"""

import base64
import logging
import io
import wave
import struct
from typing import Optional, List, Tuple
import webrtcvad

logger = logging.getLogger(__name__)

class VADProcessor:
    """Voice Activity Detection processor using WebRTC VAD"""
    
    def __init__(self, aggressiveness: int = 2):
        """
        Initialize VAD processor
        
        Args:
            aggressiveness: VAD aggressiveness level (0-3)
                           0 = least aggressive, 3 = most aggressive
        """
        self.vad = webrtcvad.Vad(aggressiveness)
        self.sample_rate = 8000  # WebRTC VAD supports 8000, 16000, 32000, 48000 Hz
        self.frame_duration_ms = 30  # WebRTC VAD supports 10, 20, 30 ms frames
        self.frame_size = int(self.sample_rate * self.frame_duration_ms / 1000)  # 240 samples for 30ms at 8kHz
        self.bytes_per_frame = self.frame_size * 2  # 16-bit audio = 2 bytes per sample
        
        logger.info(f"VAD initialized with aggressiveness={aggressiveness}, frame_size={self.frame_size}, bytes_per_frame={self.bytes_per_frame}")
    
    def has_speech(self, audio_b64: str) -> bool:
        """
        Check if audio chunk contains speech using WebRTC VAD
        
        Args:
            audio_b64: Base64 encoded audio data (16-bit PCM, mono, 8kHz)
            
        Returns:
            True if speech is detected, False otherwise
        """
        try:
            # Decode base64 audio
            audio_data = base64.b64decode(audio_b64)
            logger.debug(f"VAD processing audio chunk: {len(audio_data)} bytes")
            
            # Validate audio data length
            if len(audio_data) < self.bytes_per_frame:
                logger.debug(f"Audio chunk too small for VAD: {len(audio_data)} bytes < {self.bytes_per_frame} bytes")
                return False
            
            # Split audio into frames for VAD processing
            frames = self._split_into_frames(audio_data)
            
            if not frames:
                logger.debug("No valid frames extracted from audio chunk")
                return False
            
            # Check each frame for speech
            speech_frames = 0
            total_frames = len(frames)
            
            for frame in frames:
                try:
                    if self.vad.is_speech(frame, self.sample_rate):
                        speech_frames += 1
                except Exception as e:
                    logger.debug(f"VAD error on frame: {e}")
                    continue
            
            # Calculate speech ratio
            speech_ratio = speech_frames / total_frames if total_frames > 0 else 0
            has_speech = speech_ratio > 0.3  # At least 30% of frames should contain speech
            
            logger.debug(f"VAD result: {speech_frames}/{total_frames} frames contain speech (ratio: {speech_ratio:.2f}) -> {'SPEECH' if has_speech else 'NO SPEECH'}")
            
            return has_speech
            
        except Exception as e:
            logger.error(f"Error in VAD processing: {e}")
            # If VAD fails, assume there might be speech to avoid missing content
            return True
    
    def _split_into_frames(self, audio_data: bytes) -> List[bytes]:
        """
        Split audio data into frames suitable for WebRTC VAD
        
        Args:
            audio_data: Raw 16-bit PCM audio data
            
        Returns:
            List of audio frames
        """
        frames = []
        
        # Ensure audio data length is multiple of frame size
        total_bytes = len(audio_data)
        num_complete_frames = total_bytes // self.bytes_per_frame
        
        logger.debug(f"Splitting {total_bytes} bytes into {num_complete_frames} frames of {self.bytes_per_frame} bytes each")
        
        for i in range(num_complete_frames):
            start_idx = i * self.bytes_per_frame
            end_idx = start_idx + self.bytes_per_frame
            frame = audio_data[start_idx:end_idx]
            
            # Validate frame size
            if len(frame) == self.bytes_per_frame:
                frames.append(frame)
            else:
                logger.debug(f"Skipping incomplete frame: {len(frame)} bytes")
        
        return frames
    
    def get_speech_segments(self, audio_b64: str, min_speech_duration_ms: int = 100) -> List[Tuple[int, int]]:
        """
        Get speech segments from audio chunk
        
        Args:
            audio_b64: Base64 encoded audio data
            min_speech_duration_ms: Minimum duration for a speech segment
            
        Returns:
            List of (start_ms, end_ms) tuples for speech segments
        """
        try:
            audio_data = base64.b64decode(audio_b64)
            frames = self._split_into_frames(audio_data)
            
            if not frames:
                return []
            
            # Detect speech in each frame
            speech_frames = []
            for i, frame in enumerate(frames):
                try:
                    is_speech = self.vad.is_speech(frame, self.sample_rate)
                    speech_frames.append(is_speech)
                except:
                    speech_frames.append(False)
            
            # Find continuous speech segments
            segments = []
            start_frame = None
            
            for i, is_speech in enumerate(speech_frames):
                if is_speech and start_frame is None:
                    start_frame = i
                elif not is_speech and start_frame is not None:
                    # End of speech segment
                    start_ms = start_frame * self.frame_duration_ms
                    end_ms = i * self.frame_duration_ms
                    duration_ms = end_ms - start_ms
                    
                    if duration_ms >= min_speech_duration_ms:
                        segments.append((start_ms, end_ms))
                    
                    start_frame = None
            
            # Handle case where speech continues to the end
            if start_frame is not None:
                start_ms = start_frame * self.frame_duration_ms
                end_ms = len(speech_frames) * self.frame_duration_ms
                duration_ms = end_ms - start_ms
                
                if duration_ms >= min_speech_duration_ms:
                    segments.append((start_ms, end_ms))
            
            logger.debug(f"Found {len(segments)} speech segments: {segments}")
            return segments
            
        except Exception as e:
            logger.error(f"Error finding speech segments: {e}")
            return []
    
    def filter_speech_audio(self, audio_b64: str) -> Optional[str]:
        """
        Filter audio to keep only speech segments
        
        Args:
            audio_b64: Base64 encoded audio data
            
        Returns:
            Base64 encoded audio with only speech segments, or None if no speech
        """
        try:
            segments = self.get_speech_segments(audio_b64)
            
            if not segments:
                logger.debug("No speech segments found, returning None")
                return None
            
            audio_data = base64.b64decode(audio_b64)
            
            # Extract speech segments
            speech_data = b''
            bytes_per_ms = (self.sample_rate * 2) // 1000  # 16 bytes per ms at 8kHz 16-bit
            
            for start_ms, end_ms in segments:
                start_byte = start_ms * bytes_per_ms
                end_byte = end_ms * bytes_per_ms
                
                # Ensure we don't go beyond audio data
                start_byte = min(start_byte, len(audio_data))
                end_byte = min(end_byte, len(audio_data))
                
                if start_byte < end_byte:
                    speech_data += audio_data[start_byte:end_byte]
            
            if not speech_data:
                return None
            
            # Encode back to base64
            filtered_b64 = base64.b64encode(speech_data).decode('utf-8')
            
            logger.debug(f"Filtered audio: {len(audio_data)} -> {len(speech_data)} bytes ({len(segments)} segments)")
            
            return filtered_b64
            
        except Exception as e:
            logger.error(f"Error filtering speech audio: {e}")
            return audio_b64  # Return original if filtering fails
    
    def get_vad_stats(self, audio_b64: str) -> dict:
        """
        Get detailed VAD statistics for audio chunk
        
        Args:
            audio_b64: Base64 encoded audio data
            
        Returns:
            Dictionary with VAD statistics
        """
        try:
            audio_data = base64.b64decode(audio_b64)
            frames = self._split_into_frames(audio_data)
            
            if not frames:
                return {
                    'total_frames': 0,
                    'speech_frames': 0,
                    'speech_ratio': 0.0,
                    'total_duration_ms': 0,
                    'speech_duration_ms': 0,
                    'has_speech': False
                }
            
            speech_frames = 0
            for frame in frames:
                try:
                    if self.vad.is_speech(frame, self.sample_rate):
                        speech_frames += 1
                except:
                    continue
            
            total_frames = len(frames)
            speech_ratio = speech_frames / total_frames if total_frames > 0 else 0
            total_duration_ms = total_frames * self.frame_duration_ms
            speech_duration_ms = speech_frames * self.frame_duration_ms
            
            return {
                'total_frames': total_frames,
                'speech_frames': speech_frames,
                'speech_ratio': speech_ratio,
                'total_duration_ms': total_duration_ms,
                'speech_duration_ms': speech_duration_ms,
                'has_speech': speech_ratio > 0.3,
                'aggressiveness': self.vad._aggressiveness if hasattr(self.vad, '_aggressiveness') else 'unknown'
            }
            
        except Exception as e:
            logger.error(f"Error getting VAD stats: {e}")
            return {
                'error': str(e),
                'has_speech': True  # Default to True on error
            }

# Global VAD processor instance
vad_processor = VADProcessor(aggressiveness=2)  # Moderate aggressiveness