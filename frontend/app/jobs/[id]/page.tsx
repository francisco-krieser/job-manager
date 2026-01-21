'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { jobsApi, ProgressUpdate, JobResponse } from '@/lib/api';
import { JobStatusStream } from '@/lib/websocket';
import { updateJobInAllCaches } from '@/lib/jobCache';
import { useParams } from 'next/navigation';
import { useEffect } from 'react';
import Link from 'next/link';

export default function JobDetailPage() {
  const params = useParams();
  const jobId = params.id as string;
  const queryClient = useQueryClient();

  const { data: job, isLoading, error } = useQuery({
    queryKey: ['job', jobId],
    queryFn: () => jobsApi.get(jobId),
    // No refetchInterval - SSE handles real-time updates
    // Cache is just for instant display while fetching fresh data
  });

  const cancelMutation = useMutation({
    mutationFn: jobsApi.cancel,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['job', jobId] });
      queryClient.invalidateQueries({ queryKey: ['jobs'] });
    },
  });

  const resumeMutation = useMutation({
    mutationFn: jobsApi.resume,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['job', jobId] });
      queryClient.invalidateQueries({ queryKey: ['jobs'] });
    },
  });

  const pauseMutation = useMutation({
    mutationFn: jobsApi.pause,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['job', jobId] });
      queryClient.invalidateQueries({ queryKey: ['jobs'] });
    },
  });

  // Set up SSE streaming
  useEffect(() => {
    if (!jobId) return;

    const stream = new JobStatusStream();
    stream.connect(jobId);

    const unsubscribe = stream.onUpdate((update) => {
      // Update all caches immediately (no delay, no refetch needed)
      updateJobInAllCaches(queryClient, update);
    });

    return () => {
      unsubscribe();
      stream.disconnect();
    };
  }, [jobId, queryClient]);

  const getStatusBadgeClass = (status: string) => {
    return `status-badge status-${status}`;
  };

  const formatDate = (timestamp: number) => {
    return new Date(timestamp * 1000).toLocaleString();
  };


  if (isLoading) {
    return (
      <div className="container">
        <div className="loading">Loading job details...</div>
      </div>
    );
  }

  if (error || !job) {
    return (
      <div className="container">
        <div className="error">Job not found or error loading job</div>
        <Link href="/" className="button button-secondary">
          ← Back to Dashboard
        </Link>
      </div>
    );
  }

  return (
    <div className="container">
      <div className="header">
        <h1>Job Details</h1>
        <div style={{ marginTop: '1rem', display: 'flex', gap: '1rem', alignItems: 'center' }}>
          <Link href="/" className="button button-secondary">
            ← Back to Dashboard
          </Link>
        </div>
      </div>

      <div className="card">
        <div style={{ marginBottom: '1.5rem' }}>
          <div style={{ display: 'flex', gap: '1rem', alignItems: 'center', marginBottom: '1rem' }}>
            <span style={{ fontWeight: '600', fontSize: '1.1rem' }}>Job ID:</span>
            <code style={{ background: '#f5f5f5', padding: '0.25rem 0.5rem', borderRadius: '4px' }}>
              {job.job_id}
            </code>
            <span className={getStatusBadgeClass(job.status)}>{job.status}</span>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1rem' }}>
            <div>
              <strong>Type:</strong> {job.job_type}
            </div>
            <div>
              <strong>Retries:</strong> {job.retry_count} / {job.max_retries}
            </div>
            <div>
              <strong>Created:</strong> {formatDate(job.created_at)}
            </div>
            {job.started_at && (
              <div>
                <strong>Started:</strong> {formatDate(job.started_at)}
              </div>
            )}
            {job.completed_at && (
              <div>
                <strong>Completed:</strong> {formatDate(job.completed_at)}
              </div>
            )}
          </div>

          {(job.status === 'running' || job.status === 'pending') && (
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                <strong>Progress</strong>
                <span>{job.progress}%</span>
              </div>
              <div className="progress-bar">
                <div className="progress-fill" style={{ width: `${job.progress}%` }}>
                  {job.progress}%
                </div>
              </div>
            </div>
          )}

          {job.error && (
            <div style={{ marginTop: '1rem', padding: '1rem', background: '#fee', border: '1px solid #fcc', borderRadius: '4px' }}>
              <strong style={{ color: '#c33' }}>Error:</strong>
              <div style={{ color: '#c33', marginTop: '0.5rem' }}>{job.error}</div>
            </div>
          )}

          {job.result && (
            <div style={{ marginTop: '1rem', padding: '1rem', background: '#efe', border: '1px solid #cfc', borderRadius: '4px' }}>
              <strong style={{ color: '#3c3' }}>Result:</strong>
              <pre style={{ marginTop: '0.5rem', whiteSpace: 'pre-wrap', fontSize: '0.9rem' }}>
                {JSON.stringify(job.result, null, 2)}
              </pre>
            </div>
          )}

          {job.metadata && Object.keys(job.metadata).length > 0 && (
            <div style={{ marginTop: '1rem' }}>
              <strong>Metadata:</strong>
              <pre style={{ marginTop: '0.5rem', background: '#f5f5f5', padding: '0.5rem', borderRadius: '4px', fontSize: '0.9rem' }}>
                {JSON.stringify(job.metadata, null, 2)}
              </pre>
            </div>
          )}
        </div>

        <div style={{ display: 'flex', gap: '1rem', paddingTop: '1rem', borderTop: '1px solid #e0e0e0' }}>
          {job.status === 'running' && (
            <>
              <button
                className="button button-secondary"
                onClick={() => pauseMutation.mutate(job.job_id)}
                disabled={pauseMutation.isPending}
              >
                Pause
              </button>
              <button
                className="button button-danger"
                onClick={() => cancelMutation.mutate(job.job_id)}
                disabled={cancelMutation.isPending}
              >
                Cancel
              </button>
            </>
          )}
          {job.status === 'paused' && (
            <button
              className="button button-primary"
              onClick={() => resumeMutation.mutate(job.job_id)}
              disabled={resumeMutation.isPending}
            >
              Resume
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
