import React, { useState } from 'react';
import { Phone, Send, Loader2, AlertCircle, CheckCircle } from 'lucide-react';
import { CallRequest } from '../types';
import { apiService } from '../services/api';
import { KnowledgeBaseSelector } from './KnowledgeBaseSelector';

interface CallFormProps {
  onCallInitiated: () => void;
  selectedKnowledgeBaseId: string;
  onKnowledgeBaseChange: (kbId: string) => void;
}

export const CallForm: React.FC<CallFormProps> = ({
  onCallInitiated,
  selectedKnowledgeBaseId,
  onKnowledgeBaseChange
}) => {
  const [formData, setFormData] = useState<CallRequest>({
    from_number: '+918065193776',
    to_number: '+916360154904',
    flow_url: `${import.meta.env.VITE_API_URL || 'http://localhost:5000'}/flow`,
    status_callback_url: '',
    knowledge_base_id: '',
  });
  const [isLoading, setIsLoading] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const value = e.target.value;
    setFormData({
      ...formData,
      [e.target.name]: value === '' ? undefined : value,
    });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setMessage(null);

    try {
      const callData = {
        ...formData,
        knowledge_base_id: selectedKnowledgeBaseId || undefined
      };
      const response = await apiService.initiateCall(callData);
      setMessage({
        type: 'success',
        text: `Call initiated successfully! Call ID: ${response.data.call_id}`,
      });
      onCallInitiated();
    } catch (error) {
      setMessage({
        type: 'error',
        text: error instanceof Error ? error.message : 'Failed to initiate call',
      });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="bg-white rounded-xl shadow-lg p-6 border border-gray-100">
      <div className="flex items-center gap-3 mb-6">
        <div className="bg-gradient-to-r from-blue-500 to-purple-600 p-3 rounded-lg">
          <Phone className="w-6 h-6 text-white" />
        </div>
        <h2 className="text-2xl font-bold text-gray-800">Initiate Call</h2>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label htmlFor="from_number" className="block text-sm font-medium text-gray-700 mb-2">
            From Number
          </label>
          <input
            type="tel"
            id="from_number"
            name="from_number"
            value={formData.from_number}
            onChange={handleChange}
            className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all duration-200"
            placeholder="+918065193776"
            required
          />
        </div>

        <div>
          <label htmlFor="to_number" className="block text-sm font-medium text-gray-700 mb-2">
            To Number
          </label>
          <input
            type="tel"
            id="to_number"
            name="to_number"
            value={formData.to_number}
            onChange={handleChange}
            className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all duration-200"
            placeholder="+916360154904"
            required
          />
        </div>

        <div>
          <label htmlFor="flow_url" className="block text-sm font-medium text-gray-700 mb-2">
            Flow URL <span className="text-green-600">(Auto-configured - TwiML endpoint)</span>
          </label>
          <input
            type="url"
            id="flow_url"
            name="flow_url"
            value={formData.flow_url}
            onChange={handleChange}
            className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all duration-200"
            placeholder="TwiML Flow URL (auto-configured for conversation)"
            required
          />
          <p className="text-sm text-gray-500 mt-1">
            This TwiML endpoint handles call flow and enables continuous phone conversation.
          </p>
        </div>

        <div>
          <label htmlFor="status_callback_url" className="block text-sm font-medium text-gray-700 mb-2">
            Status Callback URL <span className="text-gray-400">(auto-generated if empty)</span>
          </label>
          <input
            type="url"
            id="status_callback_url"
            name="status_callback_url"
            value={formData.status_callback_url}
            onChange={handleChange}
            className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all duration-200"
            placeholder="https://your-callback-url.com (optional - will auto-generate webhook URL)"
          />
        </div>

        <KnowledgeBaseSelector
          selectedKbId={selectedKnowledgeBaseId}
          onSelectKb={onKnowledgeBaseChange}
          label="Knowledge Base (optional)"
          showActiveIndicator={false}
        />

        {message && (
          <div className={`flex items-center gap-2 p-4 rounded-lg ${
            message.type === 'success' 
              ? 'bg-green-50 text-green-800 border border-green-200' 
              : 'bg-red-50 text-red-800 border border-red-200'
          }`}>
            {message.type === 'success' ? (
              <CheckCircle className="w-5 h-5" />
            ) : (
              <AlertCircle className="w-5 h-5" />
            )}
            <span className="text-sm font-medium">{message.text}</span>
          </div>
        )}

        <button
          type="submit"
          disabled={isLoading}
          className="w-full bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 text-white font-medium py-3 px-6 rounded-lg transition-all duration-200 flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isLoading ? (
            <Loader2 className="w-5 h-5 animate-spin" />
          ) : (
            <Send className="w-5 h-5" />
          )}
          {isLoading ? 'Initiating Call...' : 'Initiate Call'}
        </button>
      </form>
    </div>
  );
};