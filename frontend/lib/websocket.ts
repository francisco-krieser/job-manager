import { ProgressUpdate } from './api';

export class JobStatusStream {
  private eventSource: EventSource | null = null;
  private listeners: Set<(update: ProgressUpdate) => void> = new Set();
  private filterJobId: string | null = null;

  connect(jobId?: string): void {
    if (this.eventSource) {
      this.disconnect();
    }

    this.filterJobId = jobId || null;
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

    // Use broadcast stream for all jobs, or per-job stream (which also uses broadcast internally)
    if (jobId) {
      // For detail view: use per-job endpoint (filters on backend)
      this.eventSource = new EventSource(`${apiUrl}/jobs/${jobId}/stream`);
    } else {
      // For list view: use broadcast endpoint (renamed to avoid route conflict)
      this.eventSource = new EventSource(`${apiUrl}/jobs/stream/events`);
    }

    this.eventSource.onmessage = (event) => {
      try {
        // Skip ping messages
        if (event.data.trim() === ': ping') {
          return;
        }

        const update: ProgressUpdate = JSON.parse(event.data);
        
        // If filterJobId is set, only process updates for that job
        if (this.filterJobId && update.job_id !== this.filterJobId) {
          return;
        }
        
        this.listeners.forEach((listener) => listener(update));
      } catch (error) {
        console.error('Error parsing SSE message:', error);
      }
    };

    this.eventSource.onerror = (error) => {
      console.error('SSE error:', error);
      // EventSource will automatically reconnect
    };
  }

  onUpdate(callback: (update: ProgressUpdate) => void): () => void {
    this.listeners.add(callback);
    return () => this.listeners.delete(callback);
  }

  disconnect(): void {
    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
    }
    this.listeners.clear();
    this.filterJobId = null;
  }
}
