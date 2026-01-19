import asyncio
from decimal import Decimal
from typing import AsyncIterator, Dict, Any
from .base import JobProcessor


def to_int(value):
    """Convert Decimal or other numeric types to int"""
    if isinstance(value, Decimal):
        return int(value)
    return int(value) if value is not None else 0


class ImageResizeJob(JobProcessor):
    """Simulates image resize job"""
    
    async def process(self) -> AsyncIterator[Dict[str, Any]]:
        images = to_int(self.job.get("metadata", {}).get("image_count", 3))
        sizes = self.job.get("metadata", {}).get("sizes", ["thumb", "medium", "large"])
        
        yield {
            "progress": 5,
            "status": "running",
            "message": "Loading images...",
            "data": {"step": "loading"}
        }
        await asyncio.sleep(1)
        
        total_operations = images * len(sizes)
        completed = 0
        
        for img_idx in range(images):
            for size in sizes:
                await asyncio.sleep(1)
                completed += 1
                progress = 5 + int(completed / total_operations * 90)
                
                yield {
                    "progress": progress,
                    "status": "running",
                    "message": f"Resizing image {img_idx + 1} to {size}...",
                    "data": {
                        "step": "resizing",
                        "image": img_idx + 1,
                        "size": size,
                        "completed": completed,
                        "total": total_operations
                    }
                }
        
        yield {
            "progress": 98,
            "status": "running",
            "message": "Optimizing images...",
            "data": {"step": "optimization"}
        }
        await asyncio.sleep(1)
        
        self.result = {
            "images_processed": images,
            "sizes": sizes,
            "status": "success",
            "output_url": f"/images/{self.job['job_id']}/"
        }
