import React, { useState, useEffect, useRef } from 'react';
import { Mic, MicOff, Phone, PhoneOff, Volume2, VolumeX, Radio } from 'lucide-react';
import { date } from 'zod';

interface AudioMessage {
  type: 'audio';
  stream_id: string;
  message_id: string;
  data: {
    audio_b64: string;
  };
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
  
  const wsRef = useRef<WebSocket | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);

  const WS_URL = `${import.meta.env.VITE_API_URL?.replace('http', 'ws') || 'ws://localhost:5000'}/media-stream`;

  useEffect(() => {
    return () => {
      disconnect();
    };
  }, []);

  const connect = async () => {
    try {
      setConnectionStatus('Connecting...');
      
      // Request microphone access
      const stream = await navigator.mediaDevices.getUserMedia({ 
        audio: {
          sampleRate: 8000,
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true
        } 
      });
      
      streamRef.current = stream;
      
      // Create WebSocket connection
      wsRef.current = new WebSocket(WS_URL);
      
      wsRef.current.onopen = () => {
        console.log('🔗 WebSocket connected');
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
        startRecording();
      };
      
      wsRef.current.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          console.log('📨 Received message:', message.type);
          
          if (message.type === 'audio' && message.data?.audio_b64) {
            playAudioResponse(message.data.audio_b64);
          }
        } catch (error) {
          console.error('❌ Error parsing WebSocket message:', error);
        }
      };
      
      wsRef.current.onclose = () => {
        console.log('🔌 WebSocket disconnected');
        setIsConnected(false);
        setIsRecording(false);
        setConnectionStatus('Disconnected');
      };
      
      wsRef.current.onerror = (error) => {
        console.error('❌ WebSocket error:', error);
        setConnectionStatus('Error');
      };
      
    } catch (error) {
      console.error('❌ Failed to connect:', error);
      setConnectionStatus('Failed to connect');
    }
  };

  const disconnect = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
    }
    
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop());
    }
    
    if (wsRef.current) {
      wsRef.current.close();
    }
    
    if (audioContextRef.current) {
      audioContextRef.current.close();
    }
    
    setIsConnected(false);
    setIsRecording(false);
    setConnectionStatus('Disconnected');
    setCurrentStreamId('');
    setMessageIdCounter(1);
  };

  const startRecording = async () => {
    if (!streamRef.current || !wsRef.current) return;
    
    try {
      // Create MediaRecorder for continuous recording
      mediaRecorderRef.current = new MediaRecorder(streamRef.current, {
        mimeType: 'audio/webm;codecs=opus'
      });
      
      mediaRecorderRef.current.ondataavailable = async (event) => {
        if (event.data.size > 0 && wsRef.current?.readyState === WebSocket.OPEN) {
          // Convert audio to base64 and send in correct format
          const audioBlob = event.data;
          const arrayBuffer = await audioBlob.arrayBuffer();
          const base64Audio = btoa(String.fromCharCode(...new Uint8Array(arrayBuffer)));
          
          const audioMessage: AudioMessage = {
            type: 'audio',
            stream_id: currentStreamId,
            message_id: messageIdCounter.toString(),
            data: {
              audio_b64: base64Audio
            }
          };
          
          // Increment message ID for next message
          setMessageIdCounter(prev => prev + 1);
          
          wsRef.current.send(JSON.stringify(audioMessage));
          console.log('🎤 Sent audio chunk:', {
            stream_id: currentStreamId,
            message_id: audioMessage.message_id,
            audio_size: base64Audio.length,
            date: base64Audio
          });
        }
      };
      
      // Record in small chunks for real-time streaming
      mediaRecorderRef.current.start(1000); // 1 second chunks
      setIsRecording(true);
      console.log('🎤 Started recording');
      
    } catch (error) {
      console.error('❌ Failed to start recording:', error);
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
      console.log('🛑 Stopped recording');
    }
  };

  const playAudioResponse = async (audioBase64: string) => {
    try {
      setIsPlaying(true);
      console.log('🔊 Playing audio response');
      
      // Create audio context if not exists
      if (!audioContextRef.current) {
        audioContextRef.current = new (window.AudioContext || (window as any).webkitAudioContext)();
      }
      
      // Decode base64 audio
      const audioData = atob(audioBase64);
      const audioArray = new Uint8Array(audioData.length);
      for (let i = 0; i < audioData.length; i++) {
        audioArray[i] = audioData.charCodeAt(i);
      }
      
      // Create audio buffer and play
      const audioBuffer = await audioContextRef.current.decodeAudioData(audioArray.buffer);
      const source = audioContextRef.current.createBufferSource();
      source.buffer = audioBuffer;
      source.connect(audioContextRef.current.destination);
      
      source.onended = () => {
        setIsPlaying(false);
        console.log('✅ Audio playback finished');
      };
      
      source.start();
      
    } catch (error) {
      console.error('❌ Failed to play audio:', error);
      setIsPlaying(false);
    }
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
            <p>🎤 Microphone: {isRecording ? 'Recording' : 'Idle'}</p>
            <p>🔊 Audio: {isPlaying ? 'Playing response' : 'Ready'}</p>
            <p>📊 Message ID: {messageIdCounter}</p>
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
          <div className="grid grid-cols-2 gap-4">
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
              onClick={disconnect}
              className="bg-red-600 hover:bg-red-700 text-white font-medium py-3 px-6 rounded-lg transition-all duration-200 flex items-center justify-center gap-2"
            >
              <PhoneOff className="w-5 h-5" />
              Disconnect
            </button>
          </div>
        )}
      </div>

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
          <li>• Microphone will start recording automatically</li>
          <li>• Speak into your microphone - audio is sent in Teler format with stream_id and message_id</li>
          <li>• AI processes your speech and responds with Sarvam AI TTS</li>
          <li>• Response audio is played back through your speakers</li>
          <li>• This simulates the same flow as a real Teler phone call</li>
        </ul>
      </div>
    </div>
  );
};