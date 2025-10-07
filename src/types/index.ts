export interface CallRequest {
  from_number: string;
  to_number: string;
  flow_url: string;
  status_callback_url?: string;
  knowledge_base_id?: string;
}

export interface CallResponse {
  call_id: string;
  status: 'initiated' | 'in-progress' | 'completed' | 'failed';
  from_number: string;
  to_number: string;
  flow_url: string;
  timestamp: string;
}

export interface ApiResponse<T> {
  success: boolean;
  data: T;
  message?: string;
  error?: string;
}

export interface CallHistoryItem extends CallResponse {
  id: number;
}