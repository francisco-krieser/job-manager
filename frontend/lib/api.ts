import axios from 'axios';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export interface JobRequest {
  job_type: 'data_processing' | 'report_generation' | 'image_resize';
  metadata?: Record<string, any>;
  max_retries?: number;
}

export interface JobResponse {
  job_id: string;
  job_type: string;
  status: 'pending' | 'running' | 'paused' | 'completed' | 'failed' | 'cancelled';
  progress: number;
  created_at: number;
  updated_at: number;
  started_at?: number;
  completed_at?: number;
  retry_count: number;
  max_retries: number;
  metadata: Record<string, any>;
  result?: Record<string, any>;
  error?: string;
  error_code?: string;
}

export interface ProgressUpdate {
  job_id: string;
  status: string;
  progress: number;
  message?: string;
  timestamp: number;
  data?: Record<string, any>;
}

export const jobsApi = {
  create: async (job: JobRequest): Promise<JobResponse> => {
    const response = await api.post<JobResponse>('/jobs', job);
    return response.data;
  },

  list: async (status?: string): Promise<JobResponse[]> => {
    const params = status ? { status } : {};
    const response = await api.get<JobResponse[]>('/jobs', { params });
    return response.data;
  },

  get: async (jobId: string): Promise<JobResponse> => {
    const response = await api.get<JobResponse>(`/jobs/${jobId}`);
    return response.data;
  },

  cancel: async (jobId: string): Promise<void> => {
    await api.post(`/jobs/${jobId}/cancel`);
  },

  resume: async (jobId: string): Promise<void> => {
    await api.post(`/jobs/${jobId}/resume`);
  },

  pause: async (jobId: string): Promise<void> => {
    await api.post(`/jobs/${jobId}/pause`);
  },
};

export default api;
