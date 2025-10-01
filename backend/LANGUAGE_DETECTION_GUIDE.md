# Language Detection and Switching Implementation

## Overview

This implementation adds dynamic language detection and switching capabilities to the voice call system using Sarvam AI's Language Identification API and multi-language support.

## Features

### 1. Language Detection During STT
- **Automatic Detection**: Each STT call now includes language information in the response
- **Text-based Detection**: Uses Sarvam AI's Language Identification API to detect language from transcribed text
- **Supported Languages**: All 22 official Indian languages plus English

### 2. Manual Language Switching
Users can request language changes during the conversation using phrases like:
- English: "switch to English", "change to Hindi", "speak in Tamil"
- Hindi: "अंग्रेजी में बोलो", "हिंदी में बदलो", "तमिल में बात करो"

### 3. Automatic Language Detection
- **Real-time Detection**: Automatically detects the language from user's speech
- **Smart Switching**: Switches conversation language when user changes language
- **Confirmation**: Sends confirmation message in the new language

### 4. Multi-language TTS Response
- AI responses are generated in the detected/selected language
- TTS uses appropriate speaker voice for each language
- Maintains language consistency throughout the conversation

## Supported Languages

| Language   | Code   | Native Name |
|------------|--------|-------------|
| English    | en-IN  | English     |
| Hindi      | hi-IN  | हिंदी        |
| Bengali    | bn-IN  | বাংলা        |
| Gujarati   | gu-IN  | ગુજરાતી      |
| Kannada    | kn-IN  | ಕನ್ನಡ        |
| Malayalam  | ml-IN  | മലയാളം      |
| Marathi    | mr-IN  | मराठी        |
| Odia       | or-IN  | ଓଡ଼ିଆ        |
| Punjabi    | pa-IN  | ਪੰਜਾਬੀ      |
| Tamil      | ta-IN  | தமிழ்        |
| Telugu     | te-IN  | తెలుగు       |

## Implementation Details

### Modified Files

#### 1. `sarvam_service.py`
**New Functions:**
- `detect_language_from_text(text)`: Detects language using Sarvam AI's Language Identification API
- `get_language_map()`: Returns mapping of language keywords to language codes
- `detect_language_switch_request(text)`: Detects if user is requesting a language switch

**Modified Functions:**
- `speech_to_text()`: Now returns a dictionary with both transcript and language information

#### 2. `websocket_handler.py`
**New State Fields:**
- `current_language`: Tracks the current conversation language (default: 'hi-IN')
- `detected_language`: Stores the detected language from transcript

**New Functions:**
- `_get_speaker_for_language(language)`: Maps language codes to appropriate TTS speakers
- `_send_language_switch_confirmation(connection_id, websocket, new_language)`: Sends confirmation in the new language

**Modified Functions:**
- `_convert_audio_to_text()`: Now accepts language parameter and returns language info
- `_generate_and_send_ai_response()`: Uses current language for TTS
- `_send_initial_greeting()`: Sends greeting in the configured language
- `_process_accumulated_audio()`: Includes language detection and switching logic

#### 3. `claude_service.py`
**New Functions:**
- `_get_language_name(language_code)`: Converts language codes to human-readable names

**Modified Functions:**
- `_build_conversation_prompt()`: Now includes language context to generate appropriate responses
- `_generate_ai_response()`: Uses language information for context-aware responses

## How It Works

### Flow Diagram

```
1. User speaks (3 seconds of audio accumulated)
   ↓
2. Speech Detection (VAD)
   ↓
3. STT with current language → Returns {transcript, language}
   ↓
4. Check for explicit language switch request
   ↓
   If switch detected:
   - Update current_language
   - Send confirmation in new language
   - Return
   ↓
5. Detect language from transcript text
   ↓
   If different from current:
   - Update current_language
   - Log auto-switch
   ↓
6. Generate AI response in current language
   ↓
7. Convert response to speech in current language
   ↓
8. Send audio response to user
```

## Example Usage

### Scenario 1: Manual Language Switch
```
User (in Hindi): "अंग्रेजी में बोलो"
System: Detects "switch to English" pattern
System: Updates language to 'en-IN'
System (in English): "I will now speak in English. How can I help you?"
```

### Scenario 2: Automatic Language Detection
```
User (in Hindi): "मुझे मदद चाहिए"
System: Detects language as 'hi-IN'
System: Continues in Hindi

User (switches to English): "Actually, tell me in English"
System: Detects language change to 'en-IN'
System: Automatically switches and responds in English
```

## Configuration

### Default Language
The default conversation language is set to Hindi (`hi-IN`). To change:

```python
# In websocket_handler.py, line 56
'current_language': 'en-IN',  # Change to desired default
```

### Language Keywords
Add more language switch keywords in `sarvam_service.py`:

```python
def get_language_map(self) -> Dict[str, str]:
    return {
        # Add your custom keywords here
        "your_keyword": "language-code",
    }
```

## API Integration

### Sarvam AI Language Detection API
**Endpoint:** `POST /text/identify-language`

**Request:**
```json
{
  "input": "Text to detect language from"
}
```

**Response:**
```json
{
  "language_code": "hi-IN",
  "script_code": "Deva"
}
```

## Performance Optimizations

1. **Fast Detection**: Language detection API typically responds in < 200ms
2. **Caching**: Current language is cached in call state to avoid repeated detections
3. **Smart Switching**: Only switches when language actually changes
4. **Efficient Processing**: Language detection happens in parallel with AI response generation

## Error Handling

- If language detection fails, defaults to `en-IN`
- If language switch request is invalid, continues with current language
- All errors are logged for debugging

## Testing

Test language switching with these phrases:

**Hindi to English:**
- "अंग्रेजी में बोलो"
- "switch to English"
- "change language to English"

**English to Hindi:**
- "speak in Hindi"
- "हिंदी में बात करो"
- "change to Hindi"

**To Other Languages:**
- "तमिल में बोलो" (Tamil)
- "speak in Kannada"
- "change to Bengali"

## Logging

The implementation includes detailed logging:
- `🌐` - Language detection/switching events
- `📝` - Transcription with language info
- `🔊` - TTS generation with language
- `✅` - Successful language operations

## Limitations

1. Language detection requires meaningful text (minimum 4 characters)
2. Some regional dialects may be detected as their parent language
3. Code-switching (mixing languages in same sentence) uses the dominant language

## Future Enhancements

Potential improvements:
1. Add confidence scores for language detection
2. Support for more granular dialect detection
3. Language preference learning based on user history
4. Multi-language conversation history with language tags
