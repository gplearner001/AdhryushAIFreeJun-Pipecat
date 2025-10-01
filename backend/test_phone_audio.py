#!/usr/bin/env python3
"""
Test script to analyze phone audio chunks and debug VAD issues
Run this to test audio chunks from phone calls
"""

import base64
import logging
import sys
import numpy as np
from vad_processor import vad_processor

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def analyze_audio_base64(audio_b64: str, label: str = "audio"):
    """Analyze a base64 encoded audio chunk"""
    try:
        # Decode
        audio_data = base64.b64decode(audio_b64)
        audio_array = np.frombuffer(audio_data, dtype=np.int16)

        # Calculate statistics
        rms = np.sqrt(np.mean(audio_array.astype(np.float32) ** 2))
        peak = np.max(np.abs(audio_array))
        mean = np.mean(audio_array)
        std = np.std(audio_array)
        zero_crossings = np.sum(np.diff(np.sign(audio_array)) != 0)
        zero_crossing_rate = zero_crossings / len(audio_array) if len(audio_array) > 0 else 0

        duration_ms = (len(audio_array) / 8000) * 1000

        print(f"\n{'='*60}")
        print(f"Audio Analysis: {label}")
        print(f"{'='*60}")
        print(f"Size: {len(audio_data)} bytes ({len(audio_array)} samples, {duration_ms:.1f}ms)")
        print(f"RMS: {rms:.2f}")
        print(f"Peak: {peak}")
        print(f"Mean: {mean:.2f}")
        print(f"Std Dev: {std:.2f}")
        print(f"Zero Crossings: {zero_crossings} (rate: {zero_crossing_rate:.4f})")
        print(f"Range: [{np.min(audio_array)}, {np.max(audio_array)}]")

        # Check for silence
        is_silence = rms < 50
        print(f"\nLikely Silence: {'YES' if is_silence else 'NO'} (threshold: RMS < 50)")

        # Test VAD
        print(f"\n{'='*60}")
        print("VAD Test Results")
        print(f"{'='*60}")

        # Test without enhancement
        has_speech_no_enhance = vad_processor.has_speech(audio_b64, enhance_audio=False)
        print(f"VAD (no enhancement): {'SPEECH DETECTED' if has_speech_no_enhance else 'NO SPEECH'}")

        # Test with enhancement
        has_speech_with_enhance = vad_processor.has_speech(audio_b64, enhance_audio=True)
        print(f"VAD (with enhancement): {'SPEECH DETECTED' if has_speech_with_enhance else 'NO SPEECH'}")

        # Get detailed VAD stats
        vad_stats = vad_processor.get_vad_stats(audio_b64)
        print(f"\nVAD Statistics:")
        print(f"  Total frames: {vad_stats.get('total_frames', 0)}")
        print(f"  Speech frames: {vad_stats.get('speech_frames', 0)}")
        print(f"  Speech ratio: {vad_stats.get('speech_ratio', 0):.2f}")
        print(f"  Speech duration: {vad_stats.get('speech_duration_ms', 0)}ms")
        print(f"  Has speech: {vad_stats.get('has_speech', False)}")

        return {
            'rms': rms,
            'peak': peak,
            'has_speech_no_enhance': has_speech_no_enhance,
            'has_speech_with_enhance': has_speech_with_enhance,
            'vad_stats': vad_stats
        }

    except Exception as e:
        logger.error(f"Error analyzing audio: {e}")
        return None

def generate_test_audio(duration_ms: int = 500, frequency: int = 440, amplitude: float = 5000) -> str:
    """Generate test audio (sine wave) for testing"""
    sample_rate = 8000
    num_samples = int(sample_rate * duration_ms / 1000)

    # Generate sine wave
    t = np.linspace(0, duration_ms / 1000, num_samples, endpoint=False)
    audio = (amplitude * np.sin(2 * np.pi * frequency * t)).astype(np.int16)

    # Encode to base64
    audio_b64 = base64.b64encode(audio.tobytes()).decode('utf-8')
    return audio_b64

def generate_silence(duration_ms: int = 500) -> str:
    """Generate silence for testing"""
    sample_rate = 8000
    num_samples = int(sample_rate * duration_ms / 1000)

    # Generate silence
    audio = np.zeros(num_samples, dtype=np.int16)

    # Encode to base64
    audio_b64 = base64.b64encode(audio.tobytes()).decode('utf-8')
    return audio_b64

def main():
    print("\n" + "="*60)
    print("Phone Audio VAD Testing Tool")
    print("="*60)

    # Test 1: Silence
    print("\n\nTEST 1: Pure Silence")
    silence = generate_silence(500)
    analyze_audio_base64(silence, "Pure Silence (500ms)")

    # Test 2: Low volume tone
    print("\n\nTEST 2: Low Volume Tone (440 Hz, amplitude 500)")
    low_tone = generate_test_audio(500, 440, 500)
    analyze_audio_base64(low_tone, "Low Volume Tone")

    # Test 3: Normal volume tone
    print("\n\nTEST 3: Normal Volume Tone (440 Hz, amplitude 5000)")
    normal_tone = generate_test_audio(500, 440, 5000)
    analyze_audio_base64(normal_tone, "Normal Volume Tone")

    # Test 4: Speech-like signal (multiple frequencies)
    print("\n\nTEST 4: Speech-like Signal (multiple frequencies)")
    # Simulate speech with varying frequencies
    sample_rate = 8000
    duration_ms = 500
    num_samples = int(sample_rate * duration_ms / 1000)
    t = np.linspace(0, duration_ms / 1000, num_samples, endpoint=False)

    # Mix of frequencies to simulate speech
    audio = (
        2000 * np.sin(2 * np.pi * 200 * t) +
        1500 * np.sin(2 * np.pi * 400 * t) +
        1000 * np.sin(2 * np.pi * 800 * t)
    ).astype(np.int16)

    speech_like = base64.b64encode(audio.tobytes()).decode('utf-8')
    analyze_audio_base64(speech_like, "Speech-like Signal")

    print("\n\n" + "="*60)
    print("Testing Complete!")
    print("="*60)
    print("\nIf you have actual phone audio chunks showing 'NO SPEECH',")
    print("paste the base64 audio data when prompted below:")
    print("="*60)

    # Allow user to paste actual phone audio
    try:
        user_input = input("\nPaste base64 audio data (or press Enter to skip): ").strip()
        if user_input:
            analyze_audio_base64(user_input, "User-provided Phone Audio")
    except KeyboardInterrupt:
        print("\nSkipped user input")

if __name__ == "__main__":
    main()
