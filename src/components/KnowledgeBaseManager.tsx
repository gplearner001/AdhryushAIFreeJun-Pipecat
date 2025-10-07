import React, { useState, useEffect } from 'react';
import { Database, Plus, Trash2, Upload, FileText, CheckCircle, XCircle, Loader } from 'lucide-react';

interface KnowledgeBase {
  id: string;
  name: string;
  description: string | null;
  user_id: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  document_count: number;
}

interface Document {
  id: string;
  knowledge_base_id: string;
  filename: string;
  file_type: string;
  file_size: number;
  processing_status: string;
  error_message: string | null;
  created_at: string;
  processed_at: string | null;
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

const fetchHeaders = {
  'Content-Type': 'application/json',
  'ngrok-skip-browser-warning': 'true'
};

export function KnowledgeBaseManager() {
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([]);
  const [selectedKb, setSelectedKb] = useState<KnowledgeBase | null>(null);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [newKbName, setNewKbName] = useState('');
  const [newKbDescription, setNewKbDescription] = useState('');

  const userId = 'demo-user-123';

  useEffect(() => {
    fetchKnowledgeBases();
  }, []);

  useEffect(() => {
    if (selectedKb) {
      fetchDocuments(selectedKb.id);
    }
  }, [selectedKb]);

  const fetchKnowledgeBases = async () => {
    try {
      setLoading(true);
      const response = await fetch(`${API_BASE_URL}/api/kb/knowledge-bases?user_id=${userId}`, {
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

  const fetchDocuments = async (kbId: string) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/kb/documents?knowledge_base_id=${kbId}`, {
        headers: { 'ngrok-skip-browser-warning': 'true' }
      });
      const data = await response.json();
      if (data.success) {
        setDocuments(data.data);
      }
    } catch (error) {
      console.error('Error fetching documents:', error);
    }
  };

  const createKnowledgeBase = async () => {
    if (!newKbName.trim()) return;

    try {
      setLoading(true);
      const response = await fetch(`${API_BASE_URL}/api/kb/knowledge-bases`, {
        method: 'POST',
        headers: fetchHeaders,
        body: JSON.stringify({
          name: newKbName,
          description: newKbDescription,
          user_id: userId
        })
      });

      const data = await response.json();
      if (data.success) {
        setNewKbName('');
        setNewKbDescription('');
        setShowCreateForm(false);
        await fetchKnowledgeBases();
      }
    } catch (error) {
      console.error('Error creating knowledge base:', error);
    } finally {
      setLoading(false);
    }
  };

  const deleteKnowledgeBase = async (kbId: string) => {
    if (!confirm('Are you sure you want to delete this knowledge base and all its documents?')) {
      return;
    }

    try {
      const response = await fetch(`${API_BASE_URL}/api/kb/knowledge-bases/${kbId}`, {
        method: 'DELETE',
        headers: { 'ngrok-skip-browser-warning': 'true' }
      });

      const data = await response.json();
      if (data.success) {
        if (selectedKb?.id === kbId) {
          setSelectedKb(null);
          setDocuments([]);
        }
        await fetchKnowledgeBases();
      }
    } catch (error) {
      console.error('Error deleting knowledge base:', error);
    }
  };

  const uploadDocument = async (event: React.ChangeEvent<HTMLInputElement>) => {
    if (!selectedKb || !event.target.files || event.target.files.length === 0) {
      return;
    }

    const files = Array.from(event.target.files);
    setUploading(true);

    for (const file of files) {
      try {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('knowledge_base_id', selectedKb.id);

        const response = await fetch(`${API_BASE_URL}/api/kb/documents/upload`, {
          method: 'POST',
          headers: { 'ngrok-skip-browser-warning': 'true' },
          body: formData
        });

        const data = await response.json();
        if (!data.success) {
          console.error(`Failed to upload ${file.name}:`, data.error);
        }
      } catch (error) {
        console.error(`Error uploading ${file.name}:`, error);
      }
    }

    setUploading(false);
    event.target.value = '';
    await fetchDocuments(selectedKb.id);
  };

  const deleteDocument = async (docId: string) => {
    if (!confirm('Are you sure you want to delete this document?')) {
      return;
    }

    try {
      const response = await fetch(`${API_BASE_URL}/api/kb/documents/${docId}`, {
        method: 'DELETE',
        headers: { 'ngrok-skip-browser-warning': 'true' }
      });

      const data = await response.json();
      if (data.success && selectedKb) {
        await fetchDocuments(selectedKb.id);
      }
    } catch (error) {
      console.error('Error deleting document:', error);
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="w-4 h-4 text-green-500" />;
      case 'failed':
        return <XCircle className="w-4 h-4 text-red-500" />;
      case 'processing':
        return <Loader className="w-4 h-4 text-blue-500 animate-spin" />;
      default:
        return <Loader className="w-4 h-4 text-gray-400" />;
    }
  };

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  };

  return (
    <div className="bg-white rounded-lg shadow-lg p-6">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <Database className="w-6 h-6 text-blue-600" />
          <h2 className="text-2xl font-bold text-gray-900">Knowledge Base Manager</h2>
        </div>
        <button
          onClick={() => setShowCreateForm(true)}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
        >
          <Plus className="w-4 h-4" />
          New Knowledge Base
        </button>
      </div>

      {showCreateForm && (
        <div className="mb-6 p-4 bg-gray-50 rounded-lg border border-gray-200">
          <h3 className="text-lg font-semibold mb-3">Create Knowledge Base</h3>
          <div className="space-y-3">
            <input
              type="text"
              placeholder="Name"
              value={newKbName}
              onChange={(e) => setNewKbName(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
            <textarea
              placeholder="Description (optional)"
              value={newKbDescription}
              onChange={(e) => setNewKbDescription(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              rows={3}
            />
            <div className="flex gap-2">
              <button
                onClick={createKnowledgeBase}
                disabled={!newKbName.trim() || loading}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-400 transition-colors"
              >
                Create
              </button>
              <button
                onClick={() => {
                  setShowCreateForm(false);
                  setNewKbName('');
                  setNewKbDescription('');
                }}
                className="px-4 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 transition-colors"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div>
          <h3 className="text-lg font-semibold mb-3">Knowledge Bases</h3>
          {loading && knowledgeBases.length === 0 ? (
            <div className="text-center py-8 text-gray-500">Loading...</div>
          ) : knowledgeBases.length === 0 ? (
            <div className="text-center py-8 text-gray-500">No knowledge bases yet</div>
          ) : (
            <div className="space-y-2">
              {knowledgeBases.map((kb) => (
                <div
                  key={kb.id}
                  className={`p-4 border rounded-lg cursor-pointer transition-all ${
                    selectedKb?.id === kb.id
                      ? 'border-blue-500 bg-blue-50'
                      : 'border-gray-200 hover:border-blue-300'
                  }`}
                  onClick={() => setSelectedKb(kb)}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <h4 className="font-semibold text-gray-900">{kb.name}</h4>
                      {kb.description && (
                        <p className="text-sm text-gray-600 mt-1">{kb.description}</p>
                      )}
                      <p className="text-xs text-gray-500 mt-2">
                        {kb.document_count} document{kb.document_count !== 1 ? 's' : ''}
                      </p>
                    </div>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        deleteKnowledgeBase(kb.id);
                      }}
                      className="text-red-500 hover:text-red-700 transition-colors"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div>
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-lg font-semibold">Documents</h3>
            {selectedKb && (
              <label className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 cursor-pointer transition-colors">
                <Upload className="w-4 h-4" />
                {uploading ? 'Uploading...' : 'Upload'}
                <input
                  type="file"
                  multiple
                  onChange={uploadDocument}
                  disabled={uploading}
                  accept=".pdf,.doc,.docx,.txt,.xls,.xlsx"
                  className="hidden"
                />
              </label>
            )}
          </div>

          {!selectedKb ? (
            <div className="text-center py-8 text-gray-500">
              Select a knowledge base to view documents
            </div>
          ) : documents.length === 0 ? (
            <div className="text-center py-8 text-gray-500">
              No documents yet. Upload files to get started.
            </div>
          ) : (
            <div className="space-y-2">
              {documents.map((doc) => (
                <div
                  key={doc.id}
                  className="p-4 border border-gray-200 rounded-lg hover:border-gray-300 transition-all"
                >
                  <div className="flex items-start justify-between">
                    <div className="flex items-start gap-3 flex-1">
                      <FileText className="w-5 h-5 text-gray-400 mt-0.5" />
                      <div className="flex-1 min-w-0">
                        <h4 className="font-medium text-gray-900 truncate">{doc.filename}</h4>
                        <div className="flex items-center gap-2 mt-1">
                          {getStatusIcon(doc.processing_status)}
                          <span className="text-xs text-gray-600 capitalize">
                            {doc.processing_status}
                          </span>
                          <span className="text-xs text-gray-400">
                            {formatFileSize(doc.file_size)}
                          </span>
                        </div>
                        {doc.error_message && (
                          <p className="text-xs text-red-500 mt-1">{doc.error_message}</p>
                        )}
                      </div>
                    </div>
                    <button
                      onClick={() => deleteDocument(doc.id)}
                      className="text-red-500 hover:text-red-700 transition-colors ml-2"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
