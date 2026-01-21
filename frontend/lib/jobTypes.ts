export type JobType = 'data_processing' | 'report_generation' | 'image_resize';

export type DataProcessingMetadata = {
  chunks: number;
  delay_seconds: number;
};

export type ReportGenerationMetadata = {
  report_type: string;
  pages: number;
};

export type ImageResizeMetadata = {
  image_count: number;
  sizes: string[];
};

export type JobMetadataMap = {
  data_processing: DataProcessingMetadata;
  report_generation: ReportGenerationMetadata;
  image_resize: ImageResizeMetadata;
};

export const DEFAULT_METADATA: Record<JobType, JobMetadataMap[JobType]> = {
  data_processing: {
    chunks: 10,
    delay_seconds: 2,
  },
  report_generation: {
    report_type: 'summary',
    pages: 5,
  },
  image_resize: {
    image_count: 3,
    sizes: ['thumb', 'medium', 'large'],
  },
};

export const getDefaultMetadata = (type: JobType): string => {
  return JSON.stringify(DEFAULT_METADATA[type], null, 2);
};
