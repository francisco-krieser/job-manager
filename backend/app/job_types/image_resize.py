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


class ImageResizeJob(JobProcessor):
    """Simulates image resize job"""
    
    async def process(self) -> AsyncIterator[Dict[str, Any]]:
        images = to_int(self.job.get("metadata", {}).get("image_count", 3))
        sizes = self.job.get("metadata", {}).get("sizes", ["thumb", "medium", "large"])
        
        # Check for resume state
        start_image_idx = 0
        start_size_idx = 0
        
        if self.resume_state:
            start_image_idx = to_int(self.resume_state.get("last_image_idx", 0))
            start_size_idx = to_int(self.resume_state.get("last_size_idx", 0))
            logger.info(f"Resuming from image {start_image_idx + 1}, size {start_size_idx + 1}")
        
        # If not resuming, do loading step
        if not self.resume_state:
            yield {
                "progress": 5,
                "status": "running",
                "message": "Loading images...",
                "data": {"step": "loading"}
            }
            await asyncio.sleep(1)
        
        total_operations = images * len(sizes)
        completed = 0
        
        # Calculate already completed operations
        if self.resume_state:
            completed = start_image_idx * len(sizes) + start_size_idx
        
        # Resume from checkpoint
        for img_idx in range(start_image_idx, images):
            # Start from checkpoint size index for the first image
            size_start_idx = start_size_idx if img_idx == start_image_idx else 0
            
            for size_idx, size in enumerate(sizes[size_start_idx:], start=size_start_idx):
                await asyncio.sleep(1)
                completed += 1
                progress = 5 + int(completed / total_operations * 90)
                
                yield {
                    "progress": progress,
                    "status": "running",
                    "message": f"Resizing image {img_idx + 1} to {size}..." + (" (resumed)" if completed == 1 and self.resume_state else ""),
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
