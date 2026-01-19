import os
import time
from typing import Dict, List, Optional, Any
import boto3
from botocore.exceptions import ClientError
import logging

logger = logging.getLogger(__name__)


class DynamoDBService:
    def __init__(self):
        self.table_name = os.getenv("DYNAMODB_TABLE", "jobs")
        self.dynamodb = boto3.resource(
            "dynamodb",
            region_name=os.getenv("AWS_REGION", "us-east-1"),
            endpoint_url=os.getenv("DYNAMODB_ENDPOINT_URL")  # For local development
        )
        self.table = self.dynamodb.Table(self.table_name)

    def create_job(self, job_id: str, job_type: str, metadata: Dict[str, Any], max_retries: int = 3) -> Dict[str, Any]:
        """Create a new job in DynamoDB"""
        now = int(time.time())
        
        job_item = {
            "job_id": job_id,
            "job_type": job_type,
            "status": "pending",
            "created_at": now,
            "updated_at": now,
            "progress": 0,
            "retry_count": 0,
            "max_retries": max_retries,
            "metadata": metadata,
            "created_by": "system"  # In production, get from auth context
        }
        
        self.table.put_item(Item=job_item)
        logger.info(f"Created job {job_id}")
        return job_item

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get a job by ID"""
        try:
            response = self.table.get_item(Key={"job_id": job_id})
            return response.get("Item")
        except ClientError as e:
            logger.error(f"Error getting job {job_id}: {e}")
            return None

    def query_jobs_by_status(self, status: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Query jobs by status using GSI"""
        try:
            response = self.table.query(
                IndexName="status-created_at-index",
                KeyConditionExpression="#status = :status",
                ExpressionAttributeNames={"#status": "status"},  # Escape reserved keyword
                ExpressionAttributeValues={":status": status},
                Limit=limit,
                ScanIndexForward=False  # Most recent first
            )
            return response.get("Items", [])
        except ClientError as e:
            logger.error(f"Error querying jobs by status {status}: {e}")
            return []

    def acquire_lock(self, job_id: str, worker_id: str) -> bool:
        """Acquire distributed lock on a job"""
        now = int(time.time())
        lock_ttl = now + 300  # 5 minutes
        
        try:
            self.table.update_item(
                Key={"job_id": job_id},
                UpdateExpression="""
                    SET lock_owner = :worker_id,
                        lock_expiry = :lock_ttl,
                        lock_ttl = :lock_ttl,
                        #status = :running,
                        started_at = :now,
                        updated_at = :now,
                        last_heartbeat = :now
                """,
                ConditionExpression="""
                    (attribute_not_exists(lock_owner) OR lock_expiry < :now)
                    AND #status = :pending
                """,
                ExpressionAttributeNames={
                    "#status": "status"  # Escape reserved keyword
                },
                ExpressionAttributeValues={
                    ":worker_id": worker_id,
                    ":lock_ttl": lock_ttl,
                    ":now": now,
                    ":running": "running",
                    ":pending": "pending"
                }
            )
            logger.info(f"Lock acquired for job {job_id} by worker {worker_id}")
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                logger.debug(f"Failed to acquire lock for job {job_id}")
                return False
            raise

    def release_lock(self, job_id: str, worker_id: str) -> bool:
        """Release lock (only if we own it)"""
        try:
            self.table.update_item(
                Key={"job_id": job_id},
                UpdateExpression="""
                    REMOVE lock_owner, lock_expiry, lock_ttl
                    SET updated_at = :now
                """,
                ConditionExpression="lock_owner = :worker_id",
                ExpressionAttributeValues={
                    ":worker_id": worker_id,
                    ":now": int(time.time())
                }
            )
            logger.info(f"Lock released for job {job_id} by worker {worker_id}")
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                logger.debug(f"Lock already released or owned by another worker")
                return False
            raise

    def refresh_lock(self, job_id: str, worker_id: str) -> bool:
        """Refresh lock expiry (heartbeat)"""
        now = int(time.time())
        lock_ttl = now + 300
        
        try:
            self.table.update_item(
                Key={"job_id": job_id},
                UpdateExpression="""
                    SET lock_expiry = :lock_ttl,
                        lock_ttl = :lock_ttl,
                        last_heartbeat = :now,
                        updated_at = :now
                """,
                ConditionExpression="lock_owner = :worker_id",
                ExpressionAttributeValues={
                    ":worker_id": worker_id,
                    ":lock_ttl": lock_ttl,
                    ":now": now
                }
            )
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                logger.warning(f"Lock lost for job {job_id}")
                return False
            raise

    def update_job_progress(self, job_id: str, progress: int, message: Optional[str] = None, data: Optional[Dict[str, Any]] = None):
        """Update job progress"""
        now = int(time.time())
        update_expr = "SET progress = :progress, updated_at = :now"
        expr_values = {
            ":progress": progress,
            ":now": now
        }
        
        if message:
            update_expr += ", intermediate_results = list_append(if_not_exists(intermediate_results, :empty_list), :update)"
            expr_values[":empty_list"] = []
            expr_values[":update"] = [{
                "timestamp": now,
                "progress": progress,
                "message": message,
                "data": data or {}
            }]
        
        self.table.update_item(
            Key={"job_id": job_id},
            UpdateExpression=update_expr,
            ExpressionAttributeValues=expr_values
        )

    def mark_job_completed(self, job_id: str, result: Optional[Dict[str, Any]] = None):
        """Mark job as completed"""
        now = int(time.time())
        update_expr = """
            SET #status = :completed,
                progress = :progress,
                completed_at = :now,
                updated_at = :now
        """
        expr_values = {
            ":completed": "completed",
            ":progress": 100,
            ":now": now
        }
        expr_names = {
            "#status": "status"
        }
        
        if result:
            update_expr += ", #result = :result"
            expr_names["#result"] = "result"  # Escape reserved keyword
            expr_values[":result"] = result
        
        update_expr += "\n            REMOVE lock_owner, lock_expiry, lock_ttl"
        
        self.table.update_item(
            Key={"job_id": job_id},
            UpdateExpression=update_expr,
            ExpressionAttributeNames=expr_names,
            ExpressionAttributeValues=expr_values
        )
        logger.info(f"Job {job_id} marked as completed")

    def mark_job_failed(self, job_id: str, error: str, error_code: Optional[str] = None):
        """Mark job as failed"""
        job = self.get_job(job_id)
        if not job:
            return
        
        retry_count = job.get("retry_count", 0)
        max_retries = job.get("max_retries", 3)
        now = int(time.time())
        
        if retry_count < max_retries:
            # Reset to pending for retry
            self.table.update_item(
                Key={"job_id": job_id},
                UpdateExpression="""
                    SET #status = :pending,
                        retry_count = :retry_count,
                        updated_at = :now,
                        #error = :error
                    REMOVE lock_owner, lock_expiry, lock_ttl
                """,
                ExpressionAttributeNames={
                    "#status": "status",
                    "#error": "error"  # Escape reserved keyword
                },
                ExpressionAttributeValues={
                    ":pending": "pending",
                    ":retry_count": retry_count + 1,
                    ":now": now,
                    ":error": error
                }
            )
            logger.info(f"Job {job_id} reset to pending for retry ({retry_count + 1}/{max_retries})")
        else:
            # Max retries exceeded
            update_expr = """
                SET #status = :failed,
                    updated_at = :now,
                    #error = :error,
                    completed_at = :now
            """
            expr_values = {
                ":failed": "failed",
                ":now": now,
                ":error": error
            }
            expr_names = {
                "#status": "status",
                "#error": "error"  # Escape reserved keyword
            }
            
            if error_code:
                update_expr += ", error_code = :error_code"
                expr_values[":error_code"] = error_code
            
            self.table.update_item(
                Key={"job_id": job_id},
                UpdateExpression=update_expr,
                ExpressionAttributeNames=expr_names,
                ExpressionAttributeValues=expr_values
            )
            logger.warning(f"Job {job_id} failed after {max_retries} retries")

    def cancel_job(self, job_id: str) -> bool:
        """Cancel a job"""
        now = int(time.time())
        try:
            self.table.update_item(
                Key={"job_id": job_id},
                UpdateExpression="""
                    SET #status = :cancelled,
                        updated_at = :now
                    REMOVE lock_owner, lock_expiry, lock_ttl
                """,
                ConditionExpression="#status <> :completed",
                ExpressionAttributeNames={
                    "#status": "status"
                },
                ExpressionAttributeValues={
                    ":cancelled": "cancelled",
                    ":completed": "completed",
                    ":now": now
                }
            )
            logger.info(f"Job {job_id} cancelled")
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                logger.warning(f"Cannot cancel completed job {job_id}")
                return False
            raise

    def resume_job(self, job_id: str) -> bool:
        """Resume a paused job"""
        now = int(time.time())
        try:
            self.table.update_item(
                Key={"job_id": job_id},
                UpdateExpression="""
                    SET #status = :pending,
                        updated_at = :now
                """,
                ConditionExpression="#status = :paused",
                ExpressionAttributeNames={
                    "#status": "status"
                },
                ExpressionAttributeValues={
                    ":pending": "pending",
                    ":paused": "paused",
                    ":now": now
                }
            )
            logger.info(f"Job {job_id} resumed")
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                logger.warning(f"Job {job_id} is not paused")
                return False
            raise

    def pause_job(self, job_id: str, worker_id: str) -> bool:
        """Pause a running job"""
        now = int(time.time())
        try:
            self.table.update_item(
                Key={"job_id": job_id},
                UpdateExpression="""
                    SET #status = :paused,
                        updated_at = :now
                    REMOVE lock_owner, lock_expiry, lock_ttl
                """,
                ConditionExpression="lock_owner = :worker_id AND #status = :running",
                ExpressionAttributeNames={
                    "#status": "status"
                },
                ExpressionAttributeValues={
                    ":paused": "paused",
                    ":worker_id": worker_id,
                    ":running": "running",
                    ":now": now
                }
            )
            logger.info(f"Job {job_id} paused")
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                logger.warning(f"Cannot pause job {job_id}")
                return False
            raise

    def get_stale_jobs(self, stale_threshold: int) -> List[Dict[str, Any]]:
        """Get jobs with expired locks (for recovery)"""
        try:
            response = self.table.query(
                IndexName="status-created_at-index",
                KeyConditionExpression="#status = :running",
                FilterExpression="lock_expiry < :threshold",
                ExpressionAttributeNames={"#status": "status"},  # Escape reserved keyword
                ExpressionAttributeValues={
                    ":running": "running",
                    ":threshold": stale_threshold
                },
                Limit=10
            )
            return response.get("Items", [])
        except ClientError as e:
            logger.error(f"Error getting stale jobs: {e}")
            return []

    def reset_stale_job(self, job_id: str, stale_threshold: int) -> bool:
        """Reset a stale job to pending"""
        try:
            self.table.update_item(
                Key={"job_id": job_id},
                UpdateExpression="""
                    SET #status = :pending,
                        updated_at = :now
                    REMOVE lock_owner, lock_expiry, lock_ttl
                """,
                ConditionExpression="lock_expiry < :threshold",
                ExpressionAttributeNames={
                    "#status": "status"
                },
                ExpressionAttributeValues={
                    ":pending": "pending",
                    ":now": int(time.time()),
                    ":threshold": stale_threshold
                }
            )
            logger.info(f"Stale job {job_id} reset to pending")
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                return False
            raise
