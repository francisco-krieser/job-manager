from typing import Dict, Any
from .base import JobProcessor
from .data_processing import DataProcessingJob
from .report_generation import ReportGenerationJob
from .image_resize import ImageResizeJob


def get_job_processor(job: Dict[str, Any]) -> JobProcessor:
    """Factory function to get the appropriate job processor"""
    job_type = job.get("job_type")
    
    processors = {
        "data_processing": DataProcessingJob,
        "report_generation": ReportGenerationJob,
        "image_resize": ImageResizeJob
    }
    
    processor_class = processors.get(job_type)
    if not processor_class:
        raise ValueError(f"Unknown job type: {job_type}")
    
    return processor_class(job)
