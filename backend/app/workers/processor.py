import os
import json
import asyncio
import signal
import sys
import time
import logging
from decimal import Decimal
from typing import Dict, Any, Optional
from app.services.dynamodb import DynamoDBService
from app.services.redis_service import RedisService
from app.services.sqs_service import SQSService
from app.job_types.factory import get_job_processor

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize services
dynamodb = DynamoDBService()
redis_service = RedisService()
sqs_service = SQSService()

# Get worker ID
WORKER_ID = os.getenv("ECS_TASK_ARN") or os.getenv("WORKER_ID") or f"worker-{os.getpid()}"

# Track active jobs for cleanup on shutdown
active_jobs: Dict[str, asyncio.Task] = {}


def signal_handler(sig, frame):
    """Handle SIGTERM gracefully"""
    logger.info("Received SIGTERM, cleaning up...")
    
    # Cancel all active job tasks
    for job_id, task in active_jobs.items():
        logger.info(f"Cancelling job {job_id}")
        task.cancel()
        try:
            dynamodb.release_lock(job_id, WORKER_ID)
        except Exception as e:
            logger.error(f"Error releasing lock for {job_id}: {e}")
    
    # Give time for cleanup
    time.sleep(2)
    sys.exit(0)


signal.signal(signal.SIGTERM, signal_handler)


def _extract_resume_state(job_type: str, progress_data: Dict[str, Any]) -> Dict[str, Any]:
    """Extract resume state from progress data based on job type"""
    if job_type == "data_processing":
        return {
            "last_chunk": progress_data.get("chunk", 0) - 1,  # -1 because we want to resume from this chunk
            "total_chunks": progress_data.get("total_chunks", 0)
        }
    elif job_type == "report_generation":
        step = progress_data.get("step", "generation")
        return {
            "current_step": step,
            "last_page": progress_data.get("page", 0) - 1 if step == "generation" else 0,
            "total_pages": progress_data.get("total_pages", 0)
        }
    elif job_type == "image_resize":
        # For image resize, we need to track both image and size indices
        # Simplified: track image index and size index
        image_num = progress_data.get("image", 1)
        size = progress_data.get("size", "")
        sizes = ["thumb", "medium", "large"]
        size_idx = sizes.index(size) if size in sizes else 0
        return {
            "last_image_idx": image_num - 1,  # Convert to 0-indexed
            "last_size_idx": size_idx,
            "total_images": progress_data.get("total", 0) // len(sizes) if progress_data.get("total") else 0,
            "total_sizes": len(sizes)
        }
    return {}


async def recover_stale_jobs():
    """Recover jobs with expired locks (self-healing)"""
    now = int(time.time())
    stale_threshold = now - 300  # 5 minutes
    
    stale_jobs = dynamodb.get_stale_jobs(stale_threshold)
    
    for job in stale_jobs:
        job_id = job["job_id"]
        logger.warning(f"Found stale job {job_id}, resetting to pending")
        
        try:
            if dynamodb.reset_stale_job(job_id, stale_threshold):
                # Send to SQS for retry
                sqs_service.send_job_message(job_id, "job_recovered")
                logger.info(f"Stale job {job_id} reset and queued for retry")
        except Exception as e:
            logger.error(f"Error recovering stale job {job_id}: {e}")


async def heartbeat_loop(job_id: str, receipt_handle: str):
    """Periodic heartbeat to extend lock and SQS visibility"""
    while True:
        await asyncio.sleep(30)  # Heartbeat every 30 seconds
        
        # Check if job is cancelled or paused
        job = dynamodb.get_job(job_id)
        if job:
            job_status = job.get("status")
            if job_status == "cancelled":
                logger.info(f"Job {job_id} cancelled, stopping heartbeat")
                break
            if job_status == "paused":
                logger.info(f"Job {job_id} paused, stopping heartbeat")
                break
        
        if not dynamodb.refresh_lock(job_id, WORKER_ID):
            logger.warning(f"Lock lost for job {job_id}, stopping heartbeat")
            break
        
        # Also refresh SQS visibility timeout
        try:
            sqs_service.change_message_visibility(receipt_handle, 300)
        except Exception as e:
            logger.error(f"Error refreshing SQS visibility: {e}")


async def process_job_with_heartbeat(job_id: str, receipt_handle: str):
    """Process job with periodic heartbeat and status checks"""
    job = dynamodb.get_job(job_id)
    if not job:
        logger.error(f"Job {job_id} not found")
        return
    
    job_type = job.get("job_type")
    logger.info(f"Processing job {job_id} of type {job_type}")
    
    try:
        # Get job processor
        processor = get_job_processor(job)
        
        # Start heartbeat task
        heartbeat_task = asyncio.create_task(
            heartbeat_loop(job_id, receipt_handle)
        )
        
        # Track current state for checkpoint
        current_state = None
        
        try:
            # Process job (yields progress updates)
            async for progress_update in processor.process():
                # Check if cancelled or paused
                current_job = dynamodb.get_job(job_id)
                if current_job:
                    job_status = current_job.get("status")
                    if job_status == "cancelled":
                        logger.info(f"Job {job_id} cancelled, stopping processing")
                        break
                    if job_status == "paused":
                        logger.info(f"Job {job_id} paused, saving checkpoint")
                        # Extract current state from progress update for checkpoint
                        resume_state = _extract_resume_state(
                            job_type,
                            progress_update.get("data", {})
                        )
                        # Only update resume_state if it doesn't exist (API route may have saved it)
                        if not current_job.get("resume_state"):
                            # Update resume_state without changing status (already paused)
                            dynamodb.update_resume_state(job_id, WORKER_ID, resume_state)
                        else:
                            logger.info(f"Checkpoint already exists for job {job_id}")
                        # Release lock and exit
                        dynamodb.release_lock(job_id, WORKER_ID)
                        break
                
                # Update current state for checkpoint
                current_state = progress_update.get("data", {})
                
                # Update progress in DynamoDB
                dynamodb.update_job_progress(
                    job_id,
                    progress_update.get("progress", 0),
                    progress_update.get("message"),
                    progress_update.get("data")
                )
                
                # Publish to Redis for streaming
                await redis_service.publish_job_update(job_id, {
                    "job_id": job_id,
                    "status": progress_update.get("status", "running"),
                    "progress": progress_update.get("progress", 0),
                    "message": progress_update.get("message"),
                    "timestamp": int(time.time()),
                    "data": progress_update.get("data")
                })
            
            # Check job status after loop - only mark as completed if still running
            # (If paused or cancelled, we already handled it above)
            final_job = dynamodb.get_job(job_id)
            if final_job and final_job.get("status") == "running":
                # Mark as completed
                result = processor.get_result()
                dynamodb.mark_job_completed(job_id, result)
                
                # Publish completion
                await redis_service.publish_job_update(job_id, {
                    "job_id": job_id,
                    "status": "completed",
                    "progress": 100,
                    "message": "Job completed successfully",
                    "timestamp": int(time.time()),
                    "result": result
                })
                
                logger.info(f"Job {job_id} completed successfully")
            else:
                # Job was paused or cancelled, don't mark as completed
                status = final_job.get("status") if final_job else "unknown"
                logger.info(f"Job {job_id} processing stopped (status: {status})")
            
        except asyncio.CancelledError:
            logger.info(f"Job {job_id} processing cancelled")
            raise
        except Exception as e:
            logger.error(f"Error processing job {job_id}: {e}", exc_info=True)
            # Mark as failed
            dynamodb.mark_job_failed(job_id, str(e))
            
            # Publish failure
            await redis_service.publish_job_update(job_id, {
                "job_id": job_id,
                "status": "failed",
                "message": f"Job failed: {str(e)}",
                "timestamp": int(time.time()),
                "error": str(e)
            })
            
            # Check if should retry
            job = dynamodb.get_job(job_id)
            if job and job.get("retry_count", 0) < job.get("max_retries", 3):
                # Calculate exponential backoff delay
                retry_count = job.get("retry_count", 0)
                # Convert to int in case it's a Decimal
                if isinstance(retry_count, Decimal):
                    retry_count = int(retry_count)
                delay_seconds = int(min(2 ** retry_count, 300))  # Max 5 minutes, ensure int
                sqs_service.send_job_message(job_id, "job_retry", delay_seconds)
                logger.info(f"Job {job_id} queued for retry in {delay_seconds} seconds")
        finally:
            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except asyncio.CancelledError:
                pass
            
    except Exception as e:
        logger.error(f"Fatal error processing job {job_id}: {e}", exc_info=True)
        dynamodb.mark_job_failed(job_id, str(e))


async def process_sqs_message(message: Dict[str, Any]):
    """Process a single SQS message"""
    receipt_handle = message.get("ReceiptHandle")
    if not receipt_handle:
        logger.error("Message missing ReceiptHandle")
        return
    
    try:
        body = json.loads(message.get("Body", "{}"))
        job_id = body.get("job_id")
        
        if not job_id:
            logger.error("Message missing job_id")
            sqs_service.delete_message(receipt_handle)
            return
        
        # Idempotency check - get current job state
        job = dynamodb.get_job(job_id)
        
        if not job:
            logger.warning(f"Job {job_id} not found, deleting message")
            sqs_service.delete_message(receipt_handle)
            return
        
        # Check if already processed (idempotency)
        status = job.get("status")
        if status in ["completed", "cancelled", "paused"]:
            logger.info(f"Job {job_id} already {status}, deleting message")
            sqs_service.delete_message(receipt_handle)
            return
        
        # Check if cancelled
        if status == "cancelled":
            logger.info(f"Job {job_id} is cancelled, deleting message")
            sqs_service.delete_message(receipt_handle)
            return
        
        # Check if paused
        if status == "paused":
            logger.info(f"Job {job_id} is paused, deleting message")
            sqs_service.delete_message(receipt_handle)
            return
        
        # Try to acquire distributed lock
        if not dynamodb.acquire_lock(job_id, WORKER_ID):
            # Another worker has the lock, delete message
            logger.debug(f"Failed to acquire lock for job {job_id}, another worker has it")
            sqs_service.delete_message(receipt_handle)
            return
        
        # Process job with heartbeat
        task = asyncio.create_task(
            process_job_with_heartbeat(job_id, receipt_handle)
        )
        active_jobs[job_id] = task
        
        try:
            await task
        finally:
            # Always release lock and delete message
            try:
                dynamodb.release_lock(job_id, WORKER_ID)
            except Exception as e:
                logger.error(f"Error releasing lock for {job_id}: {e}")
            
            sqs_service.delete_message(receipt_handle)
            active_jobs.pop(job_id, None)
            
    except Exception as e:
        logger.error(f"Error processing SQS message: {e}", exc_info=True)
        # Don't delete message on error - let it return to queue after visibility timeout


async def worker_main_loop():
    """Main worker loop - runs in each ECS container"""
    logger.info(f"Worker {WORKER_ID} starting...")
    
    while True:
        try:
            # 1. Recover stale jobs (self-healing)
            await recover_stale_jobs()
            
            # 2. Poll SQS for messages (long polling)
            messages = sqs_service.receive_messages(
                max_messages=1,
                wait_time_seconds=20,
                visibility_timeout=300
            )
            
            if messages:
                for message in messages:
                    await process_sqs_message(message)
            else:
                # No messages, small delay before next poll
                await asyncio.sleep(1)
                
        except KeyboardInterrupt:
            logger.info("Worker interrupted, shutting down...")
            break
        except Exception as e:
            logger.error(f"Worker loop error: {e}", exc_info=True)
            await asyncio.sleep(5)


async def main():
    """Main entry point"""
    logger.info(f"Starting worker {WORKER_ID}")
    
    try:
        await worker_main_loop()
    finally:
        # Cleanup
        await redis_service.close()
        logger.info("Worker shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())
