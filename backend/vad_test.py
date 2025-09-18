#!/usr/bin/env python3
"""
Test script for WebRTC VAD functionality
Tests VAD with different types of audio samples
"""

import base64
import logging
import numpy as np
import wave
import io
from vad_processor import vad_processor

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_test_audio(duration_ms: int, sample_rate: int = 8000, frequency: int = 440, amplitude: float = 0.5) -> str:
    """
    Create test audio with sine wave (simulates speech-like audio)
    
    Args:
        duration_ms: Duration in milliseconds
        sample_rate: Sample rate in Hz
        frequency: Sine wave frequency in Hz
        amplitude: Amplitude (0.0 to 1.0)
        
    Returns:
        Base64 encoded 16-bit PCM audio
    """
    samples = int(duration_ms * sample_rate / 1000)
    t = np.linspace(0, duration_ms / 1000, samples, False)
    
    # Generate sine wave
    audio_data = amplitude * np.sin(2 * np.pi * frequency * t)
    
    # Convert to 16-bit PCM
    audio_16bit = (audio_data * 32767).astype(np.int16)
    
    # Convert to bytes and base64
    audio_bytes = audio_16bit.tobytes()
    return base64.b64encode(audio_bytes).decode('utf-8')

def create_silence_audio(duration_ms: int, sample_rate: int = 8000) -> str:
    """
    Create silence audio
    
    Args:
        duration_ms: Duration in milliseconds
        sample_rate: Sample rate in Hz
        
    Returns:
        Base64 encoded silence audio
    """
    samples = int(duration_ms * sample_rate / 1000)
    audio_data = np.zeros(samples, dtype=np.int16)
    audio_bytes = audio_data.tobytes()
    return base64.b64encode(audio_bytes).decode('utf-8')

def create_noise_audio(duration_ms: int, sample_rate: int = 8000, amplitude: float = 0.1) -> str:
    """
    Create white noise audio
    
    Args:
        duration_ms: Duration in milliseconds
        sample_rate: Sample rate in Hz
        amplitude: Noise amplitude
        
    Returns:
        Base64 encoded noise audio
    """
    samples = int(duration_ms * sample_rate / 1000)
    noise_data = amplitude * np.random.normal(0, 1, samples)
    
    # Convert to 16-bit PCM
    audio_16bit = (noise_data * 32767).astype(np.int16)
    audio_bytes = audio_16bit.tobytes()
    return base64.b64encode(audio_bytes).decode('utf-8')

def test_vad_functionality():
    """Test VAD with different audio types"""
    
    print("🧪 Testing WebRTC VAD Functionality")
    print("=" * 50)
    
    # Test cases
    test_cases = [
        {
            'name': 'Silence (500ms)',
            'audio_func': lambda: create_silence_audio(500),
            'expected_speech': False
        },
        {
            'name': 'Short Tone (100ms, 440Hz)',
            'audio_func': lambda: create_test_audio(100, frequency=440, amplitude=0.7),
            'expected_speech': False  # Too short
        },
        {
            'name': 'Long Tone (1000ms, 440Hz)',
            'audio_func': lambda: create_test_audio(1000, frequency=440, amplitude=0.7),
            'expected_speech': True  # Should be detected as speech-like
        },
        {
            'name': 'Speech-like Tone (800ms, 200Hz)',
            'audio_func': lambda: create_test_audio(800, frequency=200, amplitude=0.8),
            'expected_speech': True  # Lower frequency, more speech-like
        },
        {
            'name': 'High Frequency Tone (500ms, 2000Hz)',
            'audio_func': lambda: create_test_audio(500, frequency=2000, amplitude=0.6),
            'expected_speech': False  # Too high frequency
        },
        {
            'name': 'White Noise (600ms)',
            'audio_func': lambda: create_noise_audio(600, amplitude=0.3),
            'expected_speech': False  # Should not be detected as speech
        },
        {
            'name': 'Loud White Noise (600ms)',
            'audio_func': lambda: create_noise_audio(600, amplitude=0.8),
            'expected_speech': False  # Even loud noise shouldn't be speech
        },
        {
            'name': 'Mixed: Speech + Silence',
            'audio_func': lambda: create_test_audio(400, frequency=300, amplitude=0.8) + create_silence_audio(400)[len(create_test_audio(400, frequency=300, amplitude=0.8)):],
            'expected_speech': True  # Should detect speech part
        }
    ]
    
    results = []
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n🧪 Test {i}: {test_case['name']}")
        print("-" * 30)
        
        try:
            # Generate test audio
            audio_b64 = test_case['audio_func']()
            
            # Test VAD
            has_speech = vad_processor.has_speech(audio_b64)
            
            # Get detailed stats
            stats = vad_processor.get_vad_stats(audio_b64)
            
            # Check result
            expected = test_case['expected_speech']
            passed = has_speech == expected
            
            print(f"📊 Audio length: {len(base64.b64decode(audio_b64))} bytes")
            print(f"📊 Total frames: {stats.get('total_frames', 0)}")
            print(f"📊 Speech frames: {stats.get('speech_frames', 0)}")
            print(f"📊 Speech ratio: {stats.get('speech_ratio', 0):.2f}")
            print(f"📊 Speech duration: {stats.get('speech_duration_ms', 0)}ms")
            print(f"🎯 VAD Result: {'SPEECH' if has_speech else 'NO SPEECH'}")
            print(f"🎯 Expected: {'SPEECH' if expected else 'NO SPEECH'}")
            print(f"✅ Test {'PASSED' if passed else 'FAILED'}")
            
            results.append({
                'name': test_case['name'],
                'passed': passed,
                'has_speech': has_speech,
                'expected': expected,
                'stats': stats
            })
            
        except Exception as e:
            print(f"❌ Test failed with error: {e}")
            results.append({
                'name': test_case['name'],
                'passed': False,
                'error': str(e)
            })
    
    # Summary
    print("\n" + "=" * 50)
    print("📋 TEST SUMMARY")
    print("=" * 50)
    
    passed_tests = sum(1 for r in results if r.get('passed', False))
    total_tests = len(results)
    
    print(f"✅ Passed: {passed_tests}/{total_tests}")
    print(f"❌ Failed: {total_tests - passed_tests}/{total_tests}")
    
    if passed_tests == total_tests:
        print("🎉 All tests passed! VAD is working correctly.")
    else:
        print("⚠️ Some tests failed. Check VAD configuration.")
        
        # Show failed tests
        failed_tests = [r for r in results if not r.get('passed', False)]
        for test in failed_tests:
            print(f"   ❌ {test['name']}: {test.get('error', 'Unexpected result')}")

def test_vad_aggressiveness():
    """Test different VAD aggressiveness levels"""
    
    print("\n🧪 Testing VAD Aggressiveness Levels")
    print("=" * 50)
    
    # Create test audio (moderate speech-like signal)
    test_audio = create_test_audio(800, frequency=300, amplitude=0.5)
    
    for aggressiveness in range(4):  # 0, 1, 2, 3
        print(f"\n🎯 Testing aggressiveness level {aggressiveness}")
        print("-" * 30)
        
        try:
            # Create VAD with specific aggressiveness
            from vad_processor import VADProcessor
            vad = VADProcessor(aggressiveness=aggressiveness)
            
            # Test VAD
            has_speech = vad.has_speech(test_audio)
            stats = vad.get_vad_stats(test_audio)
            
            print(f"📊 Speech ratio: {stats.get('speech_ratio', 0):.2f}")
            print(f"🎯 Result: {'SPEECH' if has_speech else 'NO SPEECH'}")
            
        except Exception as e:
            print(f"❌ Error with aggressiveness {aggressiveness}: {e}")

if __name__ == "__main__":
    try:
        # Test basic VAD functionality
        test_vad_functionality()
        
        # Test different aggressiveness levels
        test_vad_aggressiveness()
        
        print("\n🏁 VAD testing completed!")
        
    except Exception as e:
        logger.error(f"❌ VAD testing failed: {e}")
        print(f"❌ VAD testing failed: {e}")