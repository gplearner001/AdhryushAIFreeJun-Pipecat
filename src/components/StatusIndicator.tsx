import React, { useState, useEffect } from 'react';
import { Wifi, WifiOff, AlertTriangle } from 'lucide-react';
import { apiService } from '../services/api';

export const StatusIndicator: React.FC = () => {
  const [isConnected, setIsConnected] = useState<boolean | null>(null);

  useEffect(() => {
    const checkConnection = async () => {
      try {
        await apiService.checkHealth();
        setIsConnected(true);
      } catch (error) {
        setIsConnected(false);
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
  );
};