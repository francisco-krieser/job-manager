'use client';

import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { jobsApi, JobRequest } from '@/lib/api';
import { useRouter } from 'next/navigation';
import Link from 'next/link';

export default function NewJobPage() {
  const router = useRouter();
  const [jobType, setJobType] = useState<'data_processing' | 'report_generation' | 'image_resize'>('data_processing');
  const [metadata, setMetadata] = useState('{}');
  const [maxRetries, setMaxRetries] = useState(3);

  const createMutation = useMutation({
    mutationFn: jobsApi.create,
    onSuccess: (job) => {
      router.push(`/jobs/${job.job_id}`);
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    
    let parsedMetadata = {};
    try {
      parsedMetadata = JSON.parse(metadata);
    } catch (error) {
      alert('Invalid JSON in metadata field');
      return;
    }

    const jobRequest: JobRequest = {
      job_type: jobType,
      metadata: parsedMetadata,
      max_retries: maxRetries,
    };

    createMutation.mutate(jobRequest);
  };

  const getDefaultMetadata = (type: string) => {
    switch (type) {
      case 'data_processing':
        return JSON.stringify({ chunks: 10, delay_seconds: 2 }, null, 2);
      case 'report_generation':
        return JSON.stringify({ report_type: 'summary', pages: 5 }, null, 2);
      case 'image_resize':
        return JSON.stringify({ image_count: 3, sizes: ['thumb', 'medium', 'large'] }, null, 2);
      default:
        return '{}';
    }
  };

  const handleJobTypeChange = (newType: string) => {
    setJobType(newType as any);
    setMetadata(getDefaultMetadata(newType));
  };

  return (
    <div className="container">
      <div className="header">
        <h1>Create New Job</h1>
        <Link href="/" className="button button-secondary">
          ← Back to Dashboard
        </Link>
      </div>

      <div className="card">
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label>Job Type</label>
            <select value={jobType} onChange={(e) => handleJobTypeChange(e.target.value)}>
              <option value="data_processing">Data Processing</option>
              <option value="report_generation">Report Generation</option>
              <option value="image_resize">Image Resize</option>
            </select>
          </div>

          <div className="form-group">
            <label>Metadata (JSON)</label>
            <textarea
              value={metadata}
              onChange={(e) => setMetadata(e.target.value)}
              placeholder='{"key": "value"}'
            />
            <small style={{ color: '#666', marginTop: '0.25rem', display: 'block' }}>
              Job-specific parameters. Use valid JSON format.
            </small>
          </div>

          <div className="form-group">
            <label>Max Retries</label>
            <input
              type="number"
              min="0"
              max="10"
              value={maxRetries}
              onChange={(e) => setMaxRetries(parseInt(e.target.value))}
            />
          </div>

          <div style={{ display: 'flex', gap: '1rem', marginTop: '1.5rem' }}>
            <button type="submit" className="button button-primary" disabled={createMutation.isPending}>
              {createMutation.isPending ? 'Creating...' : 'Create Job'}
            </button>
            <Link href="/" className="button button-secondary">
              Cancel
            </Link>
          </div>

          {createMutation.isError && (
            <div className="error" style={{ marginTop: '1rem' }}>
              Error creating job: {String(createMutation.error)}
            </div>
          )}
        </form>
      </div>
    </div>
  );
}
