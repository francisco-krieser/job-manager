import asyncio
import logging
from decimal import Decimal
from typing import AsyncIterator, Dict, Any
from .base import JobProcessor

logger = logging.getLogger(__name__)


def to_int(value):
    """Convert Decimal or other numeric types to int"""
    if isinstance(value, Decimal):
        return int(value)
    return int(value) if value is not None else 0


class ReportGenerationJob(JobProcessor):
    """Simulates report generation job"""
    
    async def process(self) -> AsyncIterator[Dict[str, Any]]:
        report_type = self.job.get("metadata", {}).get("report_type", "summary")
        pages = to_int(self.job.get("metadata", {}).get("pages", 5))
        
        # Check for resume state
        resume_step = None
        start_page = 0
        
        if self.resume_state:
            resume_step = self.resume_state.get("current_step")
            start_page = to_int(self.resume_state.get("last_page", 0))
            logger.info(f"Resuming from step '{resume_step}', page {start_page + 1}")
        
        # If not resuming or resuming from early steps, do data collection
        if not resume_step or resume_step in ["data_collection", None]:
            yield {
                "progress": 10,
                "status": "running",
                "message": "Gathering data...",
                "data": {"step": "data_collection"}
            }
            await asyncio.sleep(2)
        
        # If not resuming or resuming from analysis, do analysis
        if not resume_step or resume_step in ["data_collection", "analysis", None]:
            yield {
                "progress": 30,
                "status": "running",
                "message": "Analyzing data...",
                "data": {"step": "analysis"}
            }
            await asyncio.sleep(2)
        
        # Generate pages (resume from checkpoint if applicable)
        for i in range(start_page, pages):
            await asyncio.sleep(1.5)
            progress = 30 + int((i + 1) / pages * 60)
            
            yield {
                "progress": progress,
                "status": "running",
                "message": f"Generating page {i + 1} of {pages}..." + (" (resumed)" if i == start_page and self.resume_state else ""),
                "data": {
                    "step": "generation",
                    "page": i + 1,
                    "total_pages": pages
                }
            }
        
        yield {
            "progress": 95,
            "status": "running",
            "message": "Finalizing report...",
            "data": {"step": "finalization"}
        }
        await asyncio.sleep(1)
        
        self.result = {
            "report_type": report_type,
            "pages": pages,
            "status": "success",
            "file_url": f"/reports/{self.job['job_id']}.pdf"
        }
