import json
import logging
import asyncio
from typing import List, Optional, Any
from decimal import Decimal
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from app.models.job import JobRequest, JobResponse, JobStatus
from app.services.dynamodb import DynamoDBService
from app.services.redis_service import RedisService
from app.services.sqs_service import SQSService
import uuid
import time

logger = logging.getLogger(__name__)


def convert_decimals(obj: Any) -> Any:
    """Convert Decimal types to int/float for JSON serialization"""
    if isinstance(obj, Decimal):
        return int(obj) if obj % 1 == 0 else float(obj)
    elif isinstance(obj, dict):
        return {k: convert_decimals(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_decimals(item) for item in obj]
    return obj

router = APIRouter(prefix="/jobs", tags=["jobs"])

# Initialize services
dynamodb = DynamoDBService()
redis_service = RedisService()
sqs_service = SQSService()


@router.post("", response_model=JobResponse, status_code=201)
async def create_job(job_request: JobRequest):
    """Create a new job"""
    job_id = str(uuid.uuid4())
    
    try:
        job_item = dynamodb.create_job(
            job_id=job_id,
            job_type=job_request.job_type.value,
            metadata=job_request.metadata,
            max_retries=job_request.max_retries
        )
        
        # Send message to SQS for processing
        # In production, this would be handled by DynamoDB Streams + EventBridge Pipes
        # For local development, we'll send directly
        sqs_service.send_job_message(job_id, "job_created")
        
        return JobResponse(**job_item)
    except Exception as e:
        logger.error(f"Error creating job: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=List[JobResponse])
async def list_jobs(
    status: Optional[JobStatus] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=100)
):
    """List jobs with optional status filter"""
    try:
        if status:
            jobs = dynamodb.query_jobs_by_status(status.value, limit)
        else:
            # Get all statuses and combine
            all_jobs = []
            for status_val in ["pending", "running", "completed", "failed", "cancelled", "paused"]:
                jobs = dynamodb.query_jobs_by_status(status_val, limit // 6)
                all_jobs.extend(jobs)
            jobs = sorted(all_jobs, key=lambda x: x.get("created_at", 0), reverse=True)[:limit]
        
        return [JobResponse(**job) for job in jobs]
    except Exception as e:
        logger.error(f"Error listing jobs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(job_id: str):
    """Get job details"""
    job = dynamodb.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobResponse(**job)


@router.post("/{job_id}/cancel")
async def cancel_job(job_id: str):
    """Cancel a job"""
    success = dynamodb.cancel_job(job_id)
    if not success:
        raise HTTPException(status_code=400, detail="Cannot cancel completed job or job not found")
    
    # Publish cancellation event
    await redis_service.publish_job_update(job_id, {
        "job_id": job_id,
        "status": "cancelled",
        "timestamp": int(time.time())
    })
    
    return {"status": "cancelled", "job_id": job_id}


@router.post("/{job_id}/resume")
async def resume_job(job_id: str):
    """Resume a paused job"""
    success = dynamodb.resume_job(job_id)
    if not success:
        raise HTTPException(status_code=400, detail="Job is not paused or not found")
    
    # Send message to SQS for immediate processing
    sqs_service.send_job_message(job_id, "job_resumed")
    
    return {"status": "pending", "job_id": job_id}


@router.post("/{job_id}/pause")
async def pause_job(job_id: str):
    """Pause a running job"""
    # Note: In production, you'd get worker_id from context
    # For now, we'll just update status
    job = dynamodb.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job.get("status") != "running":
        raise HTTPException(status_code=400, detail="Job is not running")
    
    # Use service method to pause (releases lock and updates status)
    worker_id = job.get("lock_owner")
    if not worker_id:
        raise HTTPException(status_code=400, detail="Job is not locked by a worker")
    
    success = dynamodb.pause_job(job_id, worker_id)
    if not success:
        raise HTTPException(status_code=400, detail="Cannot pause job")
    
    # Publish pause event
    await redis_service.publish_job_update(job_id, {
        "job_id": job_id,
        "status": "paused",
        "timestamp": int(time.time())
    })
    
    return {"status": "paused", "job_id": job_id}


@router.get("/{job_id}/stream")
async def stream_job_status(job_id: str):
    """Stream job status via Server-Sent Events"""
    
    async def event_generator():
        try:
            # Send initial state from DynamoDB
            job = dynamodb.get_job(job_id)
            if job:
                initial_data = {
                    'job_id': job_id,
                    'status': job.get('status'),
                    'progress': int(job.get('progress', 0)),
                    'message': 'Initial state',
                    'timestamp': int(time.time())
                }
                # Convert Decimal types for JSON serialization
                initial_data = convert_decimals(initial_data)
                yield f"data: {json.dumps(initial_data)}\n\n"
            else:
                error_data = {
                    'error': 'Job not found',
                    'job_id': job_id
                }
                yield f"data: {json.dumps(error_data)}\n\n"
                return
            
            # Subscribe to Redis channel
            pubsub = await redis_service.subscribe_to_job(job_id)
            
            try:
                last_ping = time.time()
                while True:
                    # Send ping every 30 seconds to keep connection alive
                    if time.time() - last_ping > 30:
                        yield ": ping\n\n"
                        last_ping = time.time()
                    
                    try:
                        # Use shorter timeout and handle None response
                        message = await asyncio.wait_for(
                            pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0),
                            timeout=1.5
                        )
                        if message and message.get('type') == 'message':
                            yield f"data: {message['data']}\n\n"
                    except asyncio.TimeoutError:
                        # Timeout is expected, continue loop
                        continue
                    except Exception as e:
                        logger.error(f"Error getting message from Redis: {e}")
                        # Send error but keep connection alive
                        error_msg = {
                            'error': 'Stream error',
                            'message': str(e),
                            'timestamp': int(time.time())
                        }
                        yield f"data: {json.dumps(error_msg)}\n\n"
                        await asyncio.sleep(1)
                        continue
            finally:
                try:
                    await pubsub.unsubscribe(f"job:{job_id}")
                    await pubsub.close()
                except Exception as e:
                    logger.error(f"Error closing pubsub: {e}")
        except asyncio.CancelledError:
            # Client disconnected, this is normal
            logger.info(f"SSE stream cancelled for job {job_id}")
            raise
        except Exception as e:
            logger.error(f"Error in SSE stream for job {job_id}: {e}", exc_info=True)
            # Send final error message before closing
            try:
                error_data = {
                    'error': 'Stream closed',
                    'message': str(e),
                    'timestamp': int(time.time())
                }
                yield f"data: {json.dumps(error_data)}\n\n"
            except:
                pass
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )
