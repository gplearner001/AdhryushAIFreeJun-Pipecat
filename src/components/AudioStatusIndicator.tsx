import React, { useState, useEffect } from 'react';
import { Mic, MicOff, Volume2, AlertTriangle } from 'lucide-react';
import { apiService } from '../services/api';

interface AudioStatus {
  available: boolean;
  speech_recognition: boolean;
  openai_whisper: boolean;
  google_stt: boolean;
  services: {
    stt: string[];
    tts: string[];
  };
}

export const AudioStatusIndicator: React.FC = () => {
  const [audioStatus, setAudioStatus] = useState<AudioStatus | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const checkAudioStatus = async () => {
      try {
        const response = await fetch(`${import.meta.env.VITE_API_URL || 'http://localhost:5000'}/api/audio/status`);
        const data = await response.json();
        setAudioStatus(data.data);
      } catch (error) {
        console.error('Failed to check audio status:', error);
        setAudioStatus(null);
      } finally {
        setIsLoading(false);
      }
    };

    checkAudioStatus();
    const interval = setInterval(checkAudioStatus, 60000); // Check every minute

    return () => clearInterval(interval);
  }, []);

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 text-gray-500">
        <AlertTriangle className="w-4 h-4" />
        <span className="text-sm">Checking audio...</span>
      </div>
    );
  }

  if (!audioStatus) {
    return (
      <div className="flex items-center gap-2 text-red-600">
        <MicOff className="w-4 h-4" />
        <span className="text-sm">Audio Service Offline</span>
      </div>
    );
  }

  const hasSTT = audioStatus.services.stt.length > 0;
  const hasTTS = audioStatus.services.tts.length > 0;

  return (
    <div className={`flex items-center gap-2 ${
      audioStatus.available ? 'text-green-600' : 'text-gray-500'
    }`}>
      <div className="flex items-center gap-1">
        {hasSTT ? (
          <Mic className="w-4 h-4" />
        ) : (
          <MicOff className="w-4 h-4" />
        )}
        {hasTTS && <Volume2 className="w-4 h-4" />}
      </div>
      <span className="text-sm">
        {audioStatus.available 
          ? `Audio: ${audioStatus.services.stt.join(', ')} STT${hasTTS ? ' + TTS' : ''}` 
          : 'Audio Processing Unavailable'
        }
      </span>
    </div>
  );
};
</AudioStatusIndicator>