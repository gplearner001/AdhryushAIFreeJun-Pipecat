#!/usr/bin/env python3
"""
Audio diagnostics tool to analyze audio chunks and debug VAD issues
"""

import base64
import logging
import struct
import numpy as np

logger = logging.getLogger(__name__)

def analyze_audio_chunk(audio_b64: str, chunk_id: str = "unknown") -> dict:
    """
    Analyze audio chunk and provide detailed diagnostics

    Args:
        audio_b64: Base64 encoded audio data
        chunk_id: Identifier for logging

    Returns:
        Dictionary with diagnostic information
    """
    try:
        # Decode audio data
        audio_data = base64.b64decode(audio_b64)

        # Basic info
        total_bytes = len(audio_data)
        num_samples = total_bytes // 2  # 16-bit = 2 bytes per sample
        duration_ms = (num_samples / 8000) * 1000  # Assuming 8kHz

        # Convert to numpy array for analysis
        audio_array = np.frombuffer(audio_data, dtype=np.int16)

        # Calculate audio statistics
        rms = np.sqrt(np.mean(audio_array.astype(np.float32) ** 2))
        peak = np.max(np.abs(audio_array))
        mean = np.mean(audio_array)
        std = np.std(audio_array)

        # Check for silence (very low RMS)
        is_likely_silence = rms < 100  # Threshold for silence detection

        # Check for clipping
        is_clipped = peak >= 32767 * 0.95

        # Analyze zero crossings (speech usually has more zero crossings)
        zero_crossings = np.sum(np.diff(np.sign(audio_array)) != 0)
        zero_crossing_rate = zero_crossings / len(audio_array) if len(audio_array) > 0 else 0

        diagnostics = {
            'chunk_id': chunk_id,
            'total_bytes': total_bytes,
            'num_samples': num_samples,
            'duration_ms': duration_ms,
            'rms': float(rms),
            'peak': int(peak),
            'mean': float(mean),
            'std': float(std),
            'zero_crossings': int(zero_crossings),
            'zero_crossing_rate': float(zero_crossing_rate),
            'is_likely_silence': is_likely_silence,
            'is_clipped': is_clipped,
            'min_value': int(np.min(audio_array)),
            'max_value': int(np.max(audio_array))
        }

        logger.info(f"""
📊 Audio Diagnostics for {chunk_id}:
   Size: {total_bytes} bytes ({num_samples} samples, {duration_ms:.1f}ms)
   RMS: {rms:.2f}, Peak: {peak}, Mean: {mean:.2f}, Std: {std:.2f}
   Zero Crossings: {zero_crossings} (rate: {zero_crossing_rate:.4f})
   Range: [{np.min(audio_array)}, {np.max(audio_array)}]
   Likely Silence: {is_likely_silence}
   Clipped: {is_clipped}
""")

        return diagnostics

    except Exception as e:
        logger.error(f"Error analyzing audio chunk: {e}")
        return {
            'chunk_id': chunk_id,
            'error': str(e),
            'total_bytes': 0
        }

def suggest_vad_settings(diagnostics: dict) -> dict:
    """
    Suggest VAD settings based on audio diagnostics

    Args:
        diagnostics: Audio diagnostics dictionary

    Returns:
        Suggested VAD settings
    """
    suggestions = {
        'aggressiveness': 2,  # Default
        'reasons': []
    }

    # If RMS is very low, use less aggressive VAD
    if diagnostics.get('rms', 0) < 200:
        suggestions['aggressiveness'] = 1
        suggestions['reasons'].append("Low RMS detected - using less aggressive VAD")

    # If RMS is high, use more aggressive VAD
    if diagnostics.get('rms', 0) > 1000:
        suggestions['aggressiveness'] = 3
        suggestions['reasons'].append("High RMS detected - using more aggressive VAD")

    # If audio is likely silence, no need to process
    if diagnostics.get('is_likely_silence', False):
        suggestions['reasons'].append("Audio appears to be silence")

    # If zero crossing rate is very low, might be silence or noise
    if diagnostics.get('zero_crossing_rate', 0) < 0.01:
        suggestions['reasons'].append("Very low zero crossing rate - likely silence or DC offset")

    return suggestions

def normalize_audio(audio_b64: str, target_rms: float = 3000.0) -> str:
    """
    Normalize audio volume to a target RMS level

    Args:
        audio_b64: Base64 encoded audio data
        target_rms: Target RMS level (default: 3000)

    Returns:
        Normalized base64 encoded audio
    """
    try:
        # Decode audio data
        audio_data = base64.b64decode(audio_b64)
        audio_array = np.frombuffer(audio_data, dtype=np.int16)

        # Calculate current RMS
        current_rms = np.sqrt(np.mean(audio_array.astype(np.float32) ** 2))

        if current_rms < 10:  # Too quiet, likely silence
            logger.debug("Audio too quiet to normalize (RMS < 10)")
            return audio_b64

        # Calculate scaling factor
        scale_factor = target_rms / current_rms

        # Limit scaling to avoid extreme amplification or clipping
        scale_factor = min(scale_factor, 10.0)  # Max 10x amplification
        scale_factor = max(scale_factor, 0.1)   # Min 0.1x attenuation

        # Apply scaling
        normalized_array = audio_array.astype(np.float32) * scale_factor

        # Clip to int16 range
        normalized_array = np.clip(normalized_array, -32768, 32767)
        normalized_array = normalized_array.astype(np.int16)

        # Encode back to base64
        normalized_data = normalized_array.tobytes()
        normalized_b64 = base64.b64encode(normalized_data).decode('utf-8')

        logger.info(f"Normalized audio: RMS {current_rms:.2f} -> {target_rms:.2f} (scale: {scale_factor:.2f})")

        return normalized_b64

    except Exception as e:
        logger.error(f"Error normalizing audio: {e}")
        return audio_b64

def enhance_audio(audio_b64: str) -> str:
    """
    Enhance audio for better speech detection
    - Normalize volume
    - Remove DC offset
    - Apply simple high-pass filter

    Args:
        audio_b64: Base64 encoded audio data

    Returns:
        Enhanced base64 encoded audio
    """
    try:
        # Decode audio data
        audio_data = base64.b64decode(audio_b64)
        audio_array = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32)

        # Remove DC offset
        audio_array = audio_array - np.mean(audio_array)

        # Simple high-pass filter to remove low-frequency noise (< 80 Hz)
        # This helps improve speech clarity
        from scipy import signal
        sos = signal.butter(4, 80, 'hp', fs=8000, output='sos')
        audio_array = signal.sosfilt(sos, audio_array)

        # Normalize
        max_val = np.max(np.abs(audio_array))
        if max_val > 0:
            audio_array = audio_array * (32000 / max_val)

        # Convert back to int16
        audio_array = np.clip(audio_array, -32768, 32767).astype(np.int16)

        # Encode back to base64
        enhanced_data = audio_array.tobytes()
        enhanced_b64 = base64.b64encode(enhanced_data).decode('utf-8')

        logger.info("Audio enhanced: DC offset removed, high-pass filtered, normalized")

        return enhanced_b64

    except ImportError:
        logger.warning("scipy not available, using simple normalization")
        return normalize_audio(audio_b64)
    except Exception as e:
        logger.error(f"Error enhancing audio: {e}")
        return audio_b64
