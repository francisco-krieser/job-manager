import asyncio
import random
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


class DataProcessingJob(JobProcessor):
    """Simulates data processing job"""
    
    async def process(self) -> AsyncIterator[Dict[str, Any]]:
        chunks = to_int(self.job.get("metadata", {}).get("chunks", 10))
        delay = self.job.get("metadata", {}).get("delay_seconds", 2)
        if isinstance(delay, Decimal):
            delay = float(delay)
        
        # Check for resume state
        start_chunk = 0
        if self.resume_state:
            start_chunk = to_int(self.resume_state.get("last_chunk", 0))
            # If we already completed this chunk, start from next
            if start_chunk >= chunks:
                start_chunk = chunks - 1  # Safety check
            logger.info(f"Resuming from chunk {start_chunk + 1} of {chunks}")
        
        for i in range(start_chunk, chunks):
            # Check if cancelled
            # (In real implementation, this would check DynamoDB)
            
            # Simulate processing
            await asyncio.sleep(delay)
            
            # Calculate progress accounting for work already done
            current_progress = int((i + 1) / chunks * 100)
            
            yield {
                "progress": current_progress,
                "status": "running",
                "message": f"Processed chunk {i + 1} of {chunks}" + (" (resumed)" if i == start_chunk and self.resume_state else ""),
                "data": {
                    "chunk": i + 1,
                    "total_chunks": chunks,
                    "processed_items": (i + 1) * 100
                }
            }
        
        self.result = {
            "chunks_processed": chunks,
            "status": "success",
            "total_items": chunks * 100
        }
