import { ProgressUpdate } from './api';

export class JobStatusStream {
  private eventSource: EventSource | null = null;
  private listeners: Set<(update: ProgressUpdate) => void> = new Set();

  connect(jobId: string): void {
    if (this.eventSource) {
      this.disconnect();
    }

    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    this.eventSource = new EventSource(`${apiUrl}/jobs/${jobId}/stream`);

    this.eventSource.onmessage = (event) => {
      try {
        const update: ProgressUpdate = JSON.parse(event.data);
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
  }
}
