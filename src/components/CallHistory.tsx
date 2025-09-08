import React, { useState, useEffect } from 'react';
import { History, Phone, Clock, ExternalLink, RefreshCw, Radio } from 'lucide-react';
import { CallHistoryItem } from '../types';
import { apiService } from '../services/api';

interface CallHistoryProps {
  refreshTrigger: number;
}

export const CallHistory: React.FC<CallHistoryProps> = ({ refreshTrigger }) => {
  const [history, setHistory] = useState<CallHistoryItem[]>([]);
  const [activeCalls, setActiveCalls] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  const fetchHistory = async () => {
    setIsLoading(true);
    try {
      const [historyResponse, activeResponse] = await Promise.all([
        apiService.getCallHistory(),
        apiService.getActiveCalls()
      ]);
      setHistory(historyResponse.data);
      setActiveCalls(activeResponse.data);
    } catch (error) {
      console.error('Failed to fetch call history:', error);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchHistory();
    // Refresh active calls more frequently
    const interval = setInterval(() => {
      apiService.getActiveCalls().then(response => {
        setActiveCalls(response.data);
      }).catch(console.error);
    }, 5000);
    
    return () => clearInterval(interval);
  }, [refreshTrigger]);

  const formatTimestamp = (timestamp: string) => {
    return new Date(timestamp).toLocaleString();
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'initiated':
        return 'bg-blue-100 text-blue-800 border-blue-200';
      case 'in-progress':
      case 'ringing':
      case 'answered':
        return 'bg-yellow-100 text-yellow-800 border-yellow-200';
      case 'completed':
        return 'bg-green-100 text-green-800 border-green-200';
      case 'failed':
      case 'busy':
      case 'no-answer':
        return 'bg-red-100 text-red-800 border-red-200';
      default:
        return 'bg-gray-100 text-gray-800 border-gray-200';
    }
  };

  return (
    <div className="bg-white rounded-xl shadow-lg p-6 border border-gray-100">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <div className="bg-gradient-to-r from-purple-500 to-pink-600 p-3 rounded-lg">
            <History className="w-6 h-6 text-white" />
          </div>
          <div>
            <h2 className="text-2xl font-bold text-gray-800">Call Management</h2>
            {activeCalls.length > 0 && (
              <p className="text-sm text-green-600 flex items-center gap-1">
                <Radio className="w-4 h-4" />
                {activeCalls.length} active call{activeCalls.length !== 1 ? 's' : ''}
              </p>
            )}
          </div>
        </div>
        <button
          onClick={fetchHistory}
          disabled={isLoading}
          className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-gray-600 hover:text-gray-800 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors duration-200 disabled:opacity-50"
        >
          <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {/* Active Calls Section */}
      {activeCalls.length > 0 && (
        <div className="mb-6">
          <h3 className="text-lg font-semibold text-gray-800 mb-3 flex items-center gap-2">
            <Radio className="w-5 h-5 text-green-500" />
            Active Calls
          </h3>
          <div className="space-y-3">
            {activeCalls.map((call) => (
              <div
                key={call.call_id}
                className="border-2 border-green-200 bg-green-50 rounded-lg p-4 animate-pulse"
              >
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-3">
                    <Radio className="w-5 h-5 text-green-600 animate-pulse" />
                    <span className="font-mono text-sm text-gray-800">{call.call_id}</span>
                  </div>
                  <span className="px-3 py-1 rounded-full text-xs font-medium bg-green-100 text-green-800 border border-green-200">
                    LIVE
                  </span>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-sm">
                  <p className="text-gray-600">From: <span className="font-medium text-gray-800">{call.from}</span></p>
                  <p className="text-gray-600">To: <span className="font-medium text-gray-800">{call.to}</span></p>
                  <p className="text-gray-600">Started: <span className="font-medium text-gray-800">{formatTimestamp(call.started_at)}</span></p>
                  <p className="text-gray-600">Status: <span className="font-medium text-green-600">{call.status}</span></p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Call History Section */}
      {history.length === 0 ? (
        <div className="text-center py-8">
          <Phone className="w-12 h-12 text-gray-400 mx-auto mb-4" />
          <p className="text-gray-500">No calls initiated yet</p>
          <p className="text-sm text-gray-400 mt-1">Your call history will appear here</p>
        </div>
      ) : (
        <div>
          <h3 className="text-lg font-semibold text-gray-800 mb-3">Call History</h3>
          <div className="space-y-4">
            {history.map((call) => (
              <div
                key={call.call_id}
                className="border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow duration-200"
              >
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-3">
                    <Phone className="w-5 h-5 text-gray-600" />
                    <span className="font-mono text-sm text-gray-800">{call.call_id}</span>
                  </div>
                  <span className={`px-3 py-1 rounded-full text-xs font-medium border ${getStatusColor(call.status)}`}>
                    {call.status ? call.status.toUpperCase() : 'UNKNOWN'}
                  </span>
                </div>
                
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-3">
                  <div>
                    <p className="text-sm text-gray-600">From: <span className="font-medium text-gray-800">{call.from_number}</span></p>
                    <p className="text-sm text-gray-600">To: <span className="font-medium text-gray-800">{call.to_number}</span></p>
                  </div>
                  <div>
                    <div className="flex items-center gap-1 text-sm text-gray-600">
                      <Clock className="w-4 h-4" />
                      {formatTimestamp(call.timestamp)}
                    </div>
                  </div>
                </div>
                
                <div className="flex items-center gap-2">
                  <ExternalLink className="w-4 h-4 text-gray-400" />
                  <a
                    href={call.flow_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-sm text-blue-600 hover:text-blue-800 truncate"
                  >
                    {call.flow_url}
                  </a>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};