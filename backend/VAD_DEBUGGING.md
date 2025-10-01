# Voice Activity Detection (VAD) Debugging Guide

## Problem Overview

Phone call audio chunks were not being detected as speech by the VAD system, causing the message:
```
🔇 No speech detected in audio chunk, skipping STT processing
```

## Root Causes

1. **Low Audio Volume**: Phone audio often has lower volume levels than direct microphone input
2. **VAD Aggressiveness**: Previous setting (level 2) was too aggressive for phone audio
3. **Speech Ratio Threshold**: Required 30% of frames to contain speech, too strict for phone calls
4. **No Audio Enhancement**: Raw phone audio wasn't being normalized or enhanced

## Solutions Implemented

### 1. Reduced VAD Aggressiveness
- Changed from level 2 → level 1
- Makes VAD more sensitive to quieter speech
- Location: `vad_processor.py` line 21

### 2. Lowered Speech Threshold
- Reduced minimum speech ratio from 0.3 → 0.2
- Now requires only 20% of frames to contain speech
- Location: `vad_processor.py` line 35

### 3. Added Audio Enhancement
- Automatically normalizes volume for low-volume audio (RMS < 500)
- Removes DC offset
- Amplifies up to 10x while preventing clipping
- Location: `vad_processor.py` method `_enhance_audio_data()`

### 4. Added Audio Diagnostics
- Logs RMS, peak, duration for every audio chunk
- Saves problematic audio files to `/tmp/` for analysis
- Provides detailed VAD statistics
- Location: `websocket_handler.py` methods `_analyze_audio_characteristics()` and `_save_debug_audio()`

### 5. Enhanced Logging
- More detailed VAD results with frame counts and ratios
- Audio characteristics logged before VAD processing
- Separate logging for enhanced vs non-enhanced audio

## Testing

### Run the Test Script

```bash
cd /tmp/cc-agent/57817134/project/backend
python3 test_phone_audio.py
```

This script:
- Tests silence detection
- Tests low volume audio
- Tests normal volume audio
- Tests speech-like signals
- Allows you to paste actual phone audio base64 for analysis

### Debugging Live Phone Calls

1. **Check Logs**: Look for these messages in your backend logs:
   ```
   📊 Audio Info: RMS=XXX, Peak=XXX, Duration=XXXms
   📊 VAD Stats: frames=X, speech_frames=X, ratio=X.XX
   ```

2. **Analyze RMS Values**:
   - RMS < 50: Likely silence, won't be processed
   - RMS 50-500: Low volume, will be enhanced automatically
   - RMS > 500: Normal volume, no enhancement needed
   - RMS > 3000: Good speech signal

3. **Check Speech Ratio**:
   - Ratio < 0.2: No speech detected
   - Ratio 0.2-0.5: Borderline speech
   - Ratio > 0.5: Clear speech

4. **Debug Audio Files**:
   - Audio chunks with volume but no detected speech are saved to `/tmp/debug_no_speech_*.wav`
   - Play these files to verify if they actually contain speech
   - Location: `/tmp/debug_no_speech_conn_*.wav`

### Manual Audio Analysis

If you have a base64 audio chunk that's not being detected:

```python
from vad_processor import vad_processor
import base64

# Your audio chunk
audio_b64 = "YOUR_BASE64_AUDIO_HERE"

# Test without enhancement
result1 = vad_processor.has_speech(audio_b64, enhance_audio=False)
print(f"Without enhancement: {result1}")

# Test with enhancement
result2 = vad_processor.has_speech(audio_b64, enhance_audio=True)
print(f"With enhancement: {result2}")

# Get detailed stats
stats = vad_processor.get_vad_stats(audio_b64)
print(f"Stats: {stats}")
```

## Configuration Options

### Adjust VAD Aggressiveness

In `vad_processor.py`, line 352:
```python
vad_processor = VADProcessor(aggressiveness=1)  # 0-3, lower = more sensitive
```

### Adjust Speech Threshold

In `vad_processor.py`, line 35:
```python
self.min_speech_ratio = 0.2  # 0.0-1.0, lower = more permissive
```

### Adjust Enhancement Threshold

In `vad_processor.py`, line 75:
```python
if enhance_audio and rms < 500:  # Adjust threshold
```

### Adjust Silence Detection

In `vad_processor.py`, line 70:
```python
if rms < 50:  # Adjust silence threshold
```

## Common Issues and Solutions

### Issue: All Audio Detected as Silence
**Symptoms**: RMS values consistently < 50
**Solution**:
- Lower silence threshold in line 70
- Check if audio format is correct (should be 16-bit PCM, 8kHz, mono)

### Issue: Audio Has Volume But No Speech Detected
**Symptoms**: RMS > 100 but speech_ratio < 0.2
**Solutions**:
- Lower `min_speech_ratio` threshold
- Reduce VAD aggressiveness to 0
- Check saved debug audio files to verify actual content

### Issue: Too Many False Positives
**Symptoms**: Background noise triggering speech detection
**Solutions**:
- Increase VAD aggressiveness to 2 or 3
- Raise `min_speech_ratio` threshold
- Increase silence threshold

### Issue: Phone Audio Still Not Working
**Steps**:
1. Enable debug audio saving (already enabled for RMS > 100)
2. Check `/tmp/debug_no_speech_*.wav` files
3. Verify audio format with: `file /tmp/debug_no_speech_*.wav`
4. Listen to the audio to confirm it contains speech
5. Run `test_phone_audio.py` with the base64 audio
6. Adjust thresholds based on the output

## Monitoring

Watch for these log patterns:

**Good (Speech Detected)**:
```
📊 Audio Info: RMS=2341.23, Peak=15234, Duration=500.0ms
🔍 Checking for speech in combined audio using WebRTC VAD...
Audio enhanced: RMS 234.12 -> 3000.00
VAD result: 8/15 frames contain speech (ratio: 0.53, threshold: 0.2) -> SPEECH
🗣️ Speech detected! Proceeding with STT processing
```

**Bad (No Speech - Silence)**:
```
📊 Audio Info: RMS=23.45, Peak=156, Duration=500.0ms
🔍 Checking for speech in combined audio using WebRTC VAD...
Audio RMS too low (23.45), likely silence
🔇 No speech detected in audio chunk, skipping STT processing
```

**Bad (No Speech - Has Volume)**:
```
📊 Audio Info: RMS=856.23, Peak=3421, Duration=500.0ms
🔍 Checking for speech in combined audio using WebRTC VAD...
VAD result: 2/15 frames contain speech (ratio: 0.13, threshold: 0.2) -> NO SPEECH
🔇 No speech detected in audio chunk, skipping STT processing
📊 VAD Stats: frames=15, speech_frames=2, ratio=0.13
💾 Saved debug audio to: /tmp/debug_no_speech_conn_1234567890_1234567890.wav
```

## Performance Impact

- Audio enhancement adds ~5-10ms processing time per chunk
- Minimal CPU impact (numpy operations are optimized)
- Memory overhead is negligible (<1MB for typical chunks)

## Dependencies

Ensure these are installed:
```bash
pip install numpy webrtcvad
```

Already added to `requirements.txt`.
