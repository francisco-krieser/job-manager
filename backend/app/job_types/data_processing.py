import asyncio
import random
from decimal import Decimal
from typing import AsyncIterator, Dict, Any
from .base import JobProcessor


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
        
        for i in range(chunks):
            # Check if cancelled
            # (In real implementation, this would check DynamoDB)
            
            # Simulate processing
            await asyncio.sleep(delay)
            
            progress = int((i + 1) / chunks * 100)
            
            yield {
                "progress": progress,
                "status": "running",
                "message": f"Processed chunk {i + 1} of {chunks}",
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
