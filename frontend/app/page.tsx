'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { jobsApi, JobResponse } from '@/lib/api';
import Link from 'next/link';
import { useState } from 'react';

export default function Home() {
  const queryClient = useQueryClient();
  const [statusFilter, setStatusFilter] = useState<string>('');

  const { data: jobs, isLoading, error } = useQuery({
    queryKey: ['jobs', statusFilter],
    queryFn: () => jobsApi.list(statusFilter || undefined),
    refetchInterval: 5000, // Poll every 5 seconds
  });

  const cancelMutation = useMutation({
    mutationFn: jobsApi.cancel,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['jobs'] });
    },
  });

  const resumeMutation = useMutation({
    mutationFn: jobsApi.resume,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['jobs'] });
    },
  });

  const pauseMutation = useMutation({
    mutationFn: jobsApi.pause,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['jobs'] });
    },
  });

  const getStatusBadgeClass = (status: string) => {
    return `status-badge status-${status}`;
  };

  const formatDate = (timestamp: number) => {
    return new Date(timestamp * 1000).toLocaleString();
  };

  return (
    <div className="container">
      <div className="header">
        <h1>Jobs Management Dashboard</h1>
        <div style={{ marginTop: '1rem', display: 'flex', gap: '1rem', alignItems: 'center' }}>
          <Link href="/jobs/new" className="button button-primary">
            Create New Job
          </Link>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            style={{ padding: '0.5rem', borderRadius: '4px', border: '1px solid #ccc' }}
          >
            <option value="">All Statuses</option>
            <option value="pending">Pending</option>
            <option value="running">Running</option>
            <option value="completed">Completed</option>
            <option value="failed">Failed</option>
            <option value="cancelled">Cancelled</option>
            <option value="paused">Paused</option>
          </select>
        </div>
      </div>

      {isLoading && <div className="loading">Loading jobs...</div>}
      {error && <div className="error">Error loading jobs: {String(error)}</div>}

      {jobs && (
        <div className="job-list">
          {jobs.length === 0 ? (
            <div className="card">
              <p>No jobs found. Create a new job to get started.</p>
            </div>
          ) : (
            jobs.map((job) => (
              <div key={job.job_id} className="job-card">
                <div className="job-info">
                  <div style={{ display: 'flex', gap: '1rem', alignItems: 'center', marginBottom: '0.5rem' }}>
                    <Link href={`/jobs/${job.job_id}`} style={{ fontWeight: '600', fontSize: '1.1rem' }}>
                      {job.job_id.substring(0, 8)}...
                    </Link>
                    <span className={getStatusBadgeClass(job.status)}>{job.status}</span>
                    <span style={{ color: '#666', fontSize: '0.9rem' }}>{job.job_type}</span>
                  </div>
                  <div style={{ color: '#666', fontSize: '0.9rem' }}>
                    Created: {formatDate(job.created_at)}
                    {job.started_at && ` | Started: ${formatDate(job.started_at)}`}
                    {job.completed_at && ` | Completed: ${formatDate(job.completed_at)}`}
                  </div>
                  {job.status === 'running' && (
                    <div className="progress-bar" style={{ marginTop: '0.5rem' }}>
                      <div className="progress-fill" style={{ width: `${job.progress}%` }}>
                        {job.progress}%
                      </div>
                    </div>
                  )}
                  {job.error && (
                    <div style={{ color: '#dc3545', fontSize: '0.9rem', marginTop: '0.5rem' }}>
                      Error: {job.error}
                    </div>
                  )}
                </div>
                <div className="job-actions">
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
                  <Link href={`/jobs/${job.job_id}`} className="button button-secondary">
                    View
                  </Link>
                </div>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}
