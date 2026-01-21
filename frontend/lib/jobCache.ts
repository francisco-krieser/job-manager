import { QueryClient } from '@tanstack/react-query';
import { JobResponse, ProgressUpdate } from './api';

/**
 * Updates a job in all related React Query caches
 * This ensures consistency across detail and list views
 */
export function updateJobInAllCaches(
  queryClient: QueryClient,
  update: ProgressUpdate
) {
  // Update detail page cache
  queryClient.setQueryData(['job', update.job_id], (old: JobResponse | undefined) => {
    if (!old) return old;
    return {
      ...old,
      status: update.status as any,
      progress: update.progress,
      ...(update.data && { result: update.data }),
    };
  });

  // Update all list caches (with and without filters)
  const possibleFilters = ['', 'pending', 'running', 'completed', 'failed', 'cancelled', 'paused'];
  
  possibleFilters.forEach((filter) => {
    queryClient.setQueryData(['jobs', filter], (old: JobResponse[] | undefined) => {
      if (!old) return old;
      
      const index = old.findIndex((j) => j.job_id === update.job_id);
      if (index === -1) return old;
      
      const updated = [...old];
      updated[index] = {
        ...updated[index],
        status: update.status as any,
        progress: update.progress,
        ...(update.data && { result: update.data }),
      };
      return updated;
    });
  });
}
