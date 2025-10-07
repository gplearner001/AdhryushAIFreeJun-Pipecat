import React, { useState, useEffect } from 'react';
import { Database } from 'lucide-react';

interface KnowledgeBase {
  id: string;
  name: string;
  description: string | null;
  document_count: number;
}

interface KnowledgeBaseSelectorProps {
  selectedKbId: string;
  onSelectKb: (kbId: string) => void;
  label?: string;
  showActiveIndicator?: boolean;
  className?: string;
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export const KnowledgeBaseSelector: React.FC<KnowledgeBaseSelectorProps> = ({
  selectedKbId,
  onSelectKb,
  label = 'Knowledge Base',
  showActiveIndicator = true,
  className = ''
}) => {
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([]);
  const [loading, setLoading] = useState(false);
  const userId = 'demo-user-123';

  useEffect(() => {
    fetchKnowledgeBases();
  }, []);

  const fetchKnowledgeBases = async () => {
    try {
      setLoading(true);
      const response = await await fetch(`${API_BASE_URL}/api/kb/knowledge-bases?user_id=${userId}`, {
        headers: { 'ngrok-skip-browser-warning': 'true' }
      });
      const data = await response.json();
      if (data.success) {
        setKnowledgeBases(data.data);
      }
    } catch (error) {
      console.error('Error fetching knowledge bases:', error);
    } finally {
      setLoading(false);
    }
  };

  const selectedKb = knowledgeBases.find(kb => kb.id === selectedKbId);

  return (
    <div className={`space-y-2 ${className}`}>
      <div className="flex items-center gap-2">
        <Database className="w-4 h-4 text-gray-500" />
        <label className="text-sm font-medium text-gray-700">{label}</label>
      </div>

      <select
        value={selectedKbId}
        onChange={(e) => onSelectKb(e.target.value)}
        disabled={loading || knowledgeBases.length === 0}
        className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100 disabled:cursor-not-allowed"
      >
        <option value="">
          {loading ? 'Loading...' : knowledgeBases.length === 0 ? 'No Knowledge Bases Available' : 'No Knowledge Base (General AI)'}
        </option>
        {knowledgeBases.map((kb) => (
          <option key={kb.id} value={kb.id}>
            {kb.name} ({kb.document_count} docs)
          </option>
        ))}
      </select>

      {showActiveIndicator && selectedKbId && selectedKb && (
        <div className="flex items-center gap-2 px-3 py-2 bg-blue-50 border border-blue-200 rounded-lg text-xs text-blue-700">
          <Database className="w-3 h-3" />
          <span className="font-medium">Active:</span>
          <span>{selectedKb.name}</span>
        </div>
      )}
    </div>
  );
};
