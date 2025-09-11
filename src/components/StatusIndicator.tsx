import React, { useState, useEffect } from 'react';
import { Wifi, WifiOff, AlertTriangle, Mic, MicOff } from 'lucide-react';
import { apiService } from '../services/api';

export const StatusIndicator: React.FC = () => {
  const [isConnected, setIsConnected] = useState<boolean | null>(null);
  const [audioStatus, setAudioStatus] = useState<any>(null);

  useEffect(() => {
    const checkConnection = async () => {
      try {
        const [healthResponse, audioResponse] = await Promise.all([
          apiService.checkHealth(),
          fetch(`${import.meta.env.VITE_API_URL || 'http://localhost:5000'}/api/audio/status`).then(r => r.json())
        ]);
        setIsConnected(true);
        setAudioStatus(audioResponse.data);
      } catch (error) {
        setIsConnected(false);
        setAudioStatus(null);
      }
    };

    checkConnection();
    const interval = setInterval(checkConnection, 30000); // Check every 30 seconds

    return () => clearInterval(interval);
  }, []);

  if (isConnected === null) {
    return (
      <div className="flex items-center gap-2 text-yellow-600">
        <AlertTriangle className="w-4 h-4" />
        <span className="text-sm">Checking connection...</span>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-4">
      <div className={`flex items-center gap-2 ${
        isConnected ? 'text-green-600' : 'text-red-600'
      }`}>
        {isConnected ? (
          <Wifi className="w-4 h-4" />
        ) : (
          <WifiOff className="w-4 h-4" />
        )}
        <span className="text-sm">
          {isConnected ? 'Backend Connected' : 'Backend Offline'}
        </span>
      </div>
      
      {audioStatus && (
        <div className={`flex items-center gap-2 ${
          audioStatus.stt_available ? 'text-blue-600' : 'text-gray-500'
        }`}>
          {audioStatus.stt_available ? (
            <Mic className="w-4 h-4" />
          ) : (
            <MicOff className="w-4 h-4" />
          )}
          <span className="text-sm">
            {audioStatus.stt_available ? 'Audio Processing Active' : 'Audio Processing Offline'}
          </span>
        </div>
      )}
    </div>
  );
};