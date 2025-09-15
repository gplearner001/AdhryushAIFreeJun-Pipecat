import React, { useState, useEffect, useRef } from 'react';
import { Mic, MicOff, Phone, PhoneOff, Volume2, VolumeX, Radio, Play, Pause, Trash2, Download } from 'lucide-react';

interface AudioMessage {
  type: 'audio';
  stream_id: string;
  message_id: string;
  data: {
    audio_b64: string;
  };
}

interface RecordedChunk {
  id: string;
  timestamp: Date;
  audioBlob: Blob;
  base64Audio: string;
  messageId: string;
  duration?: number;
  isPlaying?: boolean;
}

interface StartMessage {
  type: 'start';
  account_id: string;
  call_app_id: string;
  call_id: string;
  stream_id: string;
  message_id: number;
  data: {
    encoding: string;
    sample_rate: number;
    channels: number;
  };
}

export const WebSocketAudioClient: React.FC = () => {
  const [isConnected, setIsConnected] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState<string>('Disconnected');
  const [streamInfo, setStreamInfo] = useState<any>(null);
  const [currentStreamId, setCurrentStreamId] = useState<string>('');
  const [messageIdCounter, setMessageIdCounter] = useState<number>(1);
  const [recordedChunks, setRecordedChunks] = useState<RecordedChunk[]>([]);
  const [showChunksList, setShowChunksList] = useState(false);
  
  const wsRef = useRef<WebSocket | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const playingAudioRef = useRef<HTMLAudioElement | null>(null);
  const recordingTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const WS_URL = `${import.meta.env.VITE_API_URL?.replace('http', 'wss') || 'wss://bfd1cf0ba3ee.ngrok-free.app'}/media-stream`;

  useEffect(() => {
    return () => {
      disconnect();
    };
  }, []);

  const connect = async () => {
    try {
      setConnectionStatus('Connecting...');
      
      // Request microphone access with proper constraints
      const stream = await navigator.mediaDevices.getUserMedia({ 
        audio: {
          sampleRate: 16000, // Higher sample rate for better quality
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true
        } 
      });
      
      streamRef.current = stream;
      console.log('🎤 Microphone access granted');
      
      // Create WebSocket connection
      wsRef.current = new WebSocket(WS_URL);
      
      wsRef.current.onopen = () => {
        console.log('🔗 WebSocket connected to:', WS_URL);
        setIsConnected(true);
        setConnectionStatus('Connected');
        
        // Send start message to simulate Teler's start message
        const startMessage: StartMessage = {
          type: 'start',
          account_id: 'test-account-id',
          call_app_id: 'test-app-id',
          call_id: `call_${Date.now()}`,
          stream_id: `stream_${Date.now()}`,
          message_id: 1,
          data: {
            encoding: 'audio/l16',
            sample_rate: 8000,
            channels: 1
          }
        };
        
        // Store the stream ID for audio messages
        setCurrentStreamId(startMessage.stream_id);
        setMessageIdCounter(2); // Start from 2 since start message is 1
        
        wsRef.current?.send(JSON.stringify(startMessage));
        console.log('📤 Sent start message:', startMessage);
        
        // Start recording after connection
        setTimeout(() => {
          startRecording();
        }, 1000);
      };
      
      wsRef.current.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          console.log('📨 Received message type:', message.type);
          
          if (message.type === 'audio' && message.data?.audio_b64) {
            console.log('🔊 Received audio response, playing...');
            playAudioResponse(message.data.audio_b64);
          }
        } catch (error) {
          console.error('❌ Error parsing WebSocket message:', error);
        }
      };
      
      wsRef.current.onclose = (event) => {
        console.log('🔌 WebSocket disconnected:', event.code, event.reason);
        setIsConnected(false);
        setIsRecording(false);
        setConnectionStatus('Disconnected');
      };
      
      wsRef.current.onerror = (error) => {
        console.error('❌ WebSocket error:', error);
        setConnectionStatus('Connection Error');
      };
      
    } catch (error) {
      console.error('❌ Failed to connect:', error);
      setConnectionStatus('Failed to connect - check microphone permissions');
    }
  };

  const disconnect = () => {
    console.log('🔌 Disconnecting...');
    
    if (recordingTimeoutRef.current) {
      clearTimeout(recordingTimeoutRef.current);
      recordingTimeoutRef.current = null;
    }
    
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop();
    }
    
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => {
        track.stop();
        console.log('🛑 Stopped audio track');
      });
    }
    
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.close();
    }
    
    if (audioContextRef.current && audioContextRef.current.state !== 'closed') {
      audioContextRef.current.close();
    }
    
    if (playingAudioRef.current) {
      playingAudioRef.current.pause();
      playingAudioRef.current = null;
    }
    
    setIsConnected(false);
    setIsRecording(false);
    setConnectionStatus('Disconnected');
    setCurrentStreamId('');
    setMessageIdCounter(1);
  };

  const startRecording = async () => {
    if (!streamRef.current || !wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      console.error('❌ Cannot start recording - missing stream or WebSocket');
      return;
    }
    
    try {
      console.log('🎤 Starting recording...');
      
      // Create MediaRecorder with supported format
      let mimeType = 'audio/webm;codecs=opus';
      if (!MediaRecorder.isTypeSupported(mimeType)) {
        mimeType = 'audio/webm';
        if (!MediaRecorder.isTypeSupported(mimeType)) {
          mimeType = 'audio/mp4';
          if (!MediaRecorder.isTypeSupported(mimeType)) {
            mimeType = ''; // Let browser choose
          }
        }
      }
      
      console.log('🎵 Using MIME type:', mimeType || 'browser default');
      
      const options = mimeType ? { mimeType } : {};
      mediaRecorderRef.current = new MediaRecorder(streamRef.current, options);
      
      let audioChunks: Blob[] = [];
      
      mediaRecorderRef.current.ondataavailable = (event) => {
        if (event.data && event.data.size > 0) {
          audioChunks.push(event.data);
          console.log('📦 Audio chunk received:', event.data.size, 'bytes');
        }
      };
      
      mediaRecorderRef.current.onstop = async () => {
        console.log('🛑 Recording stopped, processing', audioChunks.length, 'chunks');
        
        if (audioChunks.length > 0) {
          try {
            await processRecordedAudio(audioChunks);
          } catch (error) {
            console.error('❌ Error processing recorded audio:', error);
          }
        }
        
        audioChunks = []; // Clear chunks
      };
      
      mediaRecorderRef.current.onerror = (event) => {
        console.error('❌ MediaRecorder error:', event);
      };
      
      // Start recording with time slices
      mediaRecorderRef.current.start(2000); // 2 second chunks
      setIsRecording(true);
      console.log('✅ Recording started successfully');
      
      // Auto-stop recording after 5 seconds for testing
      recordingTimeoutRef.current = setTimeout(() => {
        if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
          console.log('⏰ Auto-stopping recording after 5 seconds');
          stopRecording();
        }
      }, 5000);
      
    } catch (error) {
      console.error('❌ Failed to start recording:', error);
      setIsRecording(false);
    }
  };

  const stopRecording = () => {
    if (recordingTimeoutRef.current) {
      clearTimeout(recordingTimeoutRef.current);
      recordingTimeoutRef.current = null;
    }
    
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
      console.log('🛑 Stopping recording...');
      mediaRecorderRef.current.stop();
      setIsRecording(false);
    }
  };

  const processRecordedAudio = async (audioChunks: Blob[]) => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      console.error('❌ WebSocket not available for sending audio');
      return;
    }
    
    try {
      console.log('🔄 Processing', audioChunks.length, 'audio chunks');
      
      // Combine all chunks into one blob
      const combinedBlob = new Blob(audioChunks, { type: audioChunks[0]?.type || 'audio/webm' });
      console.log('📦 Combined audio blob size:', combinedBlob.size, 'bytes');
      
      if (combinedBlob.size === 0) {
        console.warn('⚠️ Empty audio blob, skipping');
        return;
      }
      
      // Convert to base64 for Teler format
      const base64Audio = await convertAudioForTeler(combinedBlob);
      
      if (!base64Audio) {
        console.error('❌ Failed to convert audio to base64');
        return;
      }
      
      // Store the recorded chunk
      const chunkId = `chunk_${Date.now()}_${messageIdCounter}`;
      const recordedChunk: RecordedChunk = {
        id: chunkId,
        timestamp: new Date(),
        audioBlob: combinedBlob,
        base64Audio: base64Audio,
        messageId: messageIdCounter.toString(),
        isPlaying: false
      };
      
      setRecordedChunks(prev => [...prev, recordedChunk]);
      
      // Send audio message in Teler format
      const audioMessage: AudioMessage = {
        type: 'audio',
        stream_id: currentStreamId,
        message_id: messageIdCounter.toString(),
        data: {
          audio_b64: base64Audio
        }
      };
      
      wsRef.current.send(JSON.stringify(audioMessage));
      console.log('📤 Sent audio message:', {
        stream_id: currentStreamId,
        message_id: audioMessage.message_id,
        audio_size: base64Audio.length,
        chunk_id: chunkId
      });
      
      // Increment message ID for next message
      setMessageIdCounter(prev => prev + 1);
      
    } catch (error) {
      console.error('❌ Error processing recorded audio:', error);
    }
  };

  const convertAudioForTeler = async (audioBlob: Blob): Promise<string | null> => {
    try {
      console.log('🔄 Converting audio blob to base64...');
      
      // Simple conversion to base64
      return new Promise((resolve, reject) => {
        const reader = new FileReader();
        
        reader.onload = () => {
          try {
            const result = reader.result as string;
            // Remove data URL prefix (e.g., "data:audio/webm;base64,")
            const base64 = result.split(',')[1];
            console.log('✅ Audio converted to base64, length:', base64.length);
            resolve(base64);
          } catch (error) {
            console.error('❌ Error extracting base64:', error);
            reject(error);
          }
        };
        
        reader.onerror = () => {
          console.error('❌ FileReader error');
          reject(new Error('FileReader failed'));
        };
        
        reader.readAsDataURL(audioBlob);
      });
      
    } catch (error) {
      console.error('❌ Error converting audio for Teler:', error);
      return null;
    }
  };

  const playAudioResponse = async (audioBase64: string) => {
    try {
      setIsPlaying(true);
      console.log('🔊 Playing audio response, length:', audioBase64.length);
      
      // Create audio blob from base64
      const audioData = atob(audioBase64);
      const audioArray = new Uint8Array(audioData.length);
      for (let i = 0; i < audioData.length; i++) {
        audioArray[i] = audioData.charCodeAt(i);
      }
      
      // Create blob and play
      const audioBlob = new Blob([audioArray], { type: 'audio/mp3' });
      const audioUrl = URL.createObjectURL(audioBlob);
      
      const audio = new Audio(audioUrl);
      playingAudioRef.current = audio;
      
      audio.onended = () => {
        setIsPlaying(false);
        URL.revokeObjectURL(audioUrl);
        playingAudioRef.current = null;
        console.log('✅ Audio response playback finished');
      };
      
      audio.onerror = (error) => {
        console.error('❌ Audio playback error:', error);
        setIsPlaying(false);
        URL.revokeObjectURL(audioUrl);
        playingAudioRef.current = null;
      };
      
      await audio.play();
      
    } catch (error) {
      console.error('❌ Failed to play audio response:', error);
      setIsPlaying(false);
    }
  };

  const playAudioChunk = async (chunk: RecordedChunk) => {
    try {
      // Stop any currently playing audio
      if (playingAudioRef.current) {
        playingAudioRef.current.pause();
        playingAudioRef.current = null;
      }
      
      // Update playing state
      setRecordedChunks(prev => 
        prev.map(c => ({ 
          ...c, 
          isPlaying: c.id === chunk.id ? true : false 
        }))
      );
      
      // Create audio element and play
      const audioUrl = URL.createObjectURL(chunk.audioBlob);
      const audio = new Audio(audioUrl);
      playingAudioRef.current = audio;
      
      audio.onended = () => {
        setRecordedChunks(prev => 
          prev.map(c => ({ ...c, isPlaying: false }))
        );
        URL.revokeObjectURL(audioUrl);
        playingAudioRef.current = null;
      };
      
      audio.onerror = (error) => {
        console.error('Error playing audio chunk:', error);
        setRecordedChunks(prev => 
          prev.map(c => ({ ...c, isPlaying: false }))
        );
        URL.revokeObjectURL(audioUrl);
        playingAudioRef.current = null;
      };
      
      await audio.play();
      console.log('🔊 Playing recorded chunk:', chunk.id);
      
    } catch (error) {
      console.error('❌ Failed to play audio chunk:', error);
      setRecordedChunks(prev => 
        prev.map(c => ({ ...c, isPlaying: false }))
      );
    }
  };
  
  const stopPlayingChunk = () => {
    if (playingAudioRef.current) {
      playingAudioRef.current.pause();
      playingAudioRef.current = null;
    }
    setRecordedChunks(prev => 
      prev.map(c => ({ ...c, isPlaying: false }))
    );
  };
  
  const downloadAudioChunk = (chunk: RecordedChunk) => {
    const url = URL.createObjectURL(chunk.audioBlob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `audio_chunk_${chunk.messageId}_${chunk.timestamp.toISOString().slice(0, 19)}.webm`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };
  
  const clearAllChunks = () => {
    stopPlayingChunk();
    setRecordedChunks([]);
  };
  
  const formatTimestamp = (timestamp: Date) => {
    return timestamp.toLocaleTimeString();
  };
  
  const formatDuration = (blob: Blob) => {
    // Estimate duration based on blob size (rough approximation)
    const estimatedDuration = blob.size / 16000; // Rough estimate for WebM
    return `~${estimatedDuration.toFixed(1)}s`;
  };

  return (
    <div className="bg-white rounded-xl shadow-lg p-6 border border-gray-100">
      <div className="flex items-center gap-3 mb-6">
        <div className="bg-gradient-to-r from-green-500 to-blue-600 p-3 rounded-lg">
          <Radio className="w-6 h-6 text-white" />
        </div>
        <div>
          <h2 className="text-2xl font-bold text-gray-800">WebSocket Audio Client</h2>
          <p className="text-sm text-gray-600">Direct microphone to Teler WebSocket streaming</p>
        </div>
      </div>

      {/* Connection Status */}
      <div className="mb-6 p-4 bg-gray-50 rounded-lg">
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm font-medium text-gray-700">Connection Status:</span>
          <span className={`text-sm font-semibold ${
            isConnected ? 'text-green-600' : 'text-red-600'
          }`}>
            {connectionStatus}
          </span>
        </div>
        
        {isConnected && (
          <div className="text-xs text-gray-500 space-y-1">
            <p>🔗 WebSocket: Connected to {WS_URL}</p>
            <p>📡 Stream ID: {currentStreamId}</p>
            <p>🎤 Microphone: {isRecording ? 'Recording (auto-stops after 5s)' : 'Idle'}</p>
            <p>🔊 Audio: {isPlaying ? 'Playing response' : 'Ready'}</p>
            <p>📊 Message ID: {messageIdCounter}</p>
            <p>📦 Recorded Chunks: {recordedChunks.length}</p>
          </div>
        )}
      </div>

      {/* Audio Controls */}
      <div className="space-y-4">
        {!isConnected ? (
          <button
            onClick={connect}
            className="w-full bg-gradient-to-r from-green-600 to-blue-600 hover:from-green-700 hover:to-blue-700 text-white font-medium py-3 px-6 rounded-lg transition-all duration-200 flex items-center justify-center gap-2"
          >
            <Phone className="w-5 h-5" />
            Connect & Start Call
          </button>
        ) : (
          <div className="grid grid-cols-3 gap-4">
            <button
              onClick={isRecording ? stopRecording : startRecording}
              className={`flex items-center justify-center gap-2 py-3 px-6 rounded-lg font-medium transition-all duration-200 ${
                isRecording
                  ? 'bg-red-600 hover:bg-red-700 text-white'
                  : 'bg-green-600 hover:bg-green-700 text-white'
              }`}
            >
              {isRecording ? <MicOff className="w-5 h-5" /> : <Mic className="w-5 h-5" />}
              {isRecording ? 'Stop Recording' : 'Start Recording'}
            </button>
            
            <button
              onClick={() => setShowChunksList(!showChunksList)}
              className="bg-blue-600 hover:bg-blue-700 text-white font-medium py-3 px-6 rounded-lg transition-all duration-200 flex items-center justify-center gap-2"
            >
              <Volume2 className="w-5 h-5" />
              Chunks ({recordedChunks.length})
            </button>
            
            <button
              onClick={disconnect}
              className="bg-red-600 hover:bg-red-700 text-white font-medium py-3 px-6 rounded-lg transition-all duration-200 flex items-center justify-center gap-2"
            >
              <PhoneOff className="w-5 h-5" />
              Disconnect
            </button>
          </div>
        )}
      </div>

      {/* Recorded Chunks List */}
      {showChunksList && (
        <div className="mt-6 border-t border-gray-200 pt-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-gray-800">
              Recorded Audio Chunks ({recordedChunks.length})
            </h3>
            {recordedChunks.length > 0 && (
              <button
                onClick={clearAllChunks}
                className="text-red-600 hover:text-red-800 text-sm flex items-center gap-1"
              >
                <Trash2 className="w-4 h-4" />
                Clear All
              </button>
            )}
          </div>
          
          {recordedChunks.length === 0 ? (
            <div className="text-center py-8 text-gray-500">
              <Volume2 className="w-12 h-12 mx-auto mb-4 text-gray-300" />
              <p>No audio chunks recorded yet</p>
              <p className="text-sm text-gray-400 mt-1">Start recording to see chunks here</p>
            </div>
          ) : (
            <div className="space-y-3 max-h-64 overflow-y-auto">
              {recordedChunks.map((chunk) => (
                <div
                  key={chunk.id}
                  className="flex items-center justify-between p-3 bg-gray-50 rounded-lg border"
                >
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-sm font-medium text-gray-800">
                        Chunk #{chunk.messageId}
                      </span>
                      <span className="text-xs text-gray-500">
                        {formatTimestamp(chunk.timestamp)}
                      </span>
                    </div>
                    <div className="text-xs text-gray-600">
                      Size: {(chunk.audioBlob.size / 1024).toFixed(1)}KB • 
                      Duration: {formatDuration(chunk.audioBlob)}
                    </div>
                  </div>
                  
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => chunk.isPlaying ? stopPlayingChunk() : playAudioChunk(chunk)}
                      className={`p-2 rounded-lg transition-all duration-200 ${
                        chunk.isPlaying
                          ? 'bg-red-600 hover:bg-red-700 text-white'
                          : 'bg-green-600 hover:bg-green-700 text-white'
                      }`}
                      title={chunk.isPlaying ? 'Stop playing' : 'Play chunk'}
                    >
                      {chunk.isPlaying ? (
                        <Pause className="w-4 h-4" />
                      ) : (
                        <Play className="w-4 h-4" />
                      )}
                    </button>
                    
                    <button
                      onClick={() => downloadAudioChunk(chunk)}
                      className="p-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-all duration-200"
                      title="Download chunk"
                    >
                      <Download className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Audio Status Indicators */}
      {isConnected && (
        <div className="mt-6 flex items-center justify-center gap-6">
          <div className={`flex items-center gap-2 ${isRecording ? 'text-red-600' : 'text-gray-400'}`}>
            {isRecording ? <Mic className="w-5 h-5 animate-pulse" /> : <MicOff className="w-5 h-5" />}
            <span className="text-sm font-medium">
              {isRecording ? 'Recording...' : 'Mic Off'}
            </span>
          </div>
          
          <div className={`flex items-center gap-2 ${isPlaying ? 'text-blue-600' : 'text-gray-400'}`}>
            {isPlaying ? <Volume2 className="w-5 h-5 animate-pulse" /> : <VolumeX className="w-5 h-5" />}
            <span className="text-sm font-medium">
              {isPlaying ? 'Playing...' : 'Audio Off'}
            </span>
          </div>
        </div>
      )}

      {/* Instructions */}
      <div className="mt-6 p-4 bg-blue-50 rounded-lg border border-blue-200">
        <h3 className="text-sm font-semibold text-blue-800 mb-2">How it works:</h3>
        <ul className="text-xs text-blue-700 space-y-1">
          <li>• Click "Connect & Start Call" to establish WebSocket connection</li>
          <li>• Recording starts automatically and stops after 5 seconds (for testing)</li>
          <li>• Speak into your microphone during the recording period</li>
          <li>• Audio is processed and sent to backend in Teler format</li>
          <li>• Click "Chunks" button to view and play back recorded audio chunks</li>
          <li>• Each chunk can be played individually or downloaded for analysis</li>
          <li>• AI processes your speech and responds with Sarvam AI TTS</li>
          <li>• Response audio is played back through your speakers</li>
          <li>• Manual start/stop recording is also available</li>
        </ul>
      </div>
    </div>
  );
};