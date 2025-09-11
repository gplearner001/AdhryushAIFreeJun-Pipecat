import React, { useState, useEffect } from 'react';
import { Volume2, VolumeX, Mic, MicOff, Radio } from 'lucide-react';

interface AudioStream {
  call_id: string;
  stream_id: string;
  connection_id: string;
  status: string;
  encoding: string;
  sample_rate: number;
}

export const AudioStatusIndicator: React.FC = () => {
  const [audioStreams, setAudioStreams] = useState<AudioStream[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const fetchAudioStreams = async () => {
      try {
        const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000';
        const response = await fetch(`${API_BASE_URL}/api/websocket/streams`);
        const data = await response.json();
        
        if (data.success) {
          const streams = Object.entries(data.data).map(([connectionId, streamInfo]: [string, any]) => ({
            call_id: streamInfo.call_id || 'Unknown',
            stream_id: streamInfo.stream_id || 'Unknown',
            connection_id: connectionId,
            status: 'active',
            encoding: streamInfo.encoding || 'audio/l16',
            sample_rate: streamInfo.sample_rate || 8000
          }));
          setAudioStreams(streams);
        }
      } catch (error) {
        console.error('Failed to fetch audio streams:', error);
        setAudioStreams([]);
      } finally {
        setIsLoading(false);
      }
    };

    fetchAudioStreams();
    const interval = setInterval(fetchAudioStreams, 3000); // Update every 3 seconds

    return () => clearInterval(interval);
  }, []);

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 text-gray-500">
        <Volume2 className="w-4 h-4 animate-pulse" />
        <span className="text-sm">Checking audio streams...</span>
      </div>
    );
  }

  if (audioStreams.length === 0) {
    return (
      <div className="flex items-center gap-2 text-gray-500">
        <VolumeX className="w-4 h-4" />
        <span className="text-sm">No active audio streams</span>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2 text-green-600">
      <Radio className="w-4 h-4 animate-pulse" />
      <span className="text-sm">
        {audioStreams.length} audio stream{audioStreams.length !== 1 ? 's' : ''} active
      </span>
      <div className="flex items-center gap-1 ml-2">
        {audioStreams.map((stream, index) => (
          <div
            key={stream.connection_id}
            className="w-2 h-2 bg-green-500 rounded-full animate-pulse"
            title={`Stream: ${stream.stream_id} | ${stream.encoding} | ${stream.sample_rate}Hz`}
          />
        ))}
      </div>
    </div>
  );
};