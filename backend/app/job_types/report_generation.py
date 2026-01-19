import asyncio
from decimal import Decimal
from typing import AsyncIterator, Dict, Any
from .base import JobProcessor


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
        
        yield {
            "progress": 10,
            "status": "running",
            "message": "Gathering data...",
            "data": {"step": "data_collection"}
        }
        await asyncio.sleep(2)
        
        yield {
            "progress": 30,
            "status": "running",
            "message": "Analyzing data...",
            "data": {"step": "analysis"}
        }
        await asyncio.sleep(2)
        
        # Generate pages
        for i in range(pages):
            await asyncio.sleep(1.5)
            progress = 30 + int((i + 1) / pages * 60)
            
            yield {
                "progress": progress,
                "status": "running",
                "message": f"Generating page {i + 1} of {pages}...",
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
