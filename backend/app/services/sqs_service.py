import os
import json
import time
import logging
from typing import Dict, Any, List, Optional
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class SQSService:
    def __init__(self):
        self.queue_url = os.getenv("SQS_QUEUE_URL")
        self.sqs = boto3.client(
            "sqs",
            region_name=os.getenv("AWS_REGION", "us-east-1"),
            endpoint_url=os.getenv("SQS_ENDPOINT_URL")  # For local development
        )
        
        # If queue URL not set, try to get it from queue name
        if not self.queue_url:
            queue_name = os.getenv("SQS_QUEUE_NAME", "job-queue")
            endpoint_url = os.getenv("SQS_ENDPOINT_URL")
            region = os.getenv("AWS_REGION", "us-east-1")
            
            if endpoint_url:
                # For LocalStack, construct the URL
                if "localstack" in endpoint_url or "localhost" in endpoint_url:
                    # LocalStack format: http://sqs.region.localhost.localstack.cloud:4566/000000000000/queue-name
                    self.queue_url = f"{endpoint_url}/000000000000/{queue_name}"
                else:
                    # Try to get queue URL from AWS
                    try:
                        response = self.sqs.get_queue_url(QueueName=queue_name)
                        self.queue_url = response["QueueUrl"]
                    except Exception as e:
                        logger.warning(f"Could not get queue URL for {queue_name}: {e}")
            else:
                logger.warning("SQS_QUEUE_URL and SQS_ENDPOINT_URL not set, SQS operations will fail")

    def send_job_message(self, job_id: str, event_type: str = "job_created", delay_seconds: int = 0):
        """Send a message to SQS queue for job processing"""
        if not self.queue_url:
            logger.warning("SQS queue URL not configured")
            return
        
        message = {
            "job_id": job_id,
            "event_type": event_type,
            "timestamp": int(time.time())
        }
        
        try:
            params = {
                "QueueUrl": self.queue_url,
                "MessageBody": json.dumps(message)
            }
            if delay_seconds > 0:
                params["DelaySeconds"] = delay_seconds
            
            response = self.sqs.send_message(**params)
            logger.info(f"Sent message to SQS for job {job_id}: {response['MessageId']}")
            return response
        except ClientError as e:
            logger.error(f"Error sending message to SQS: {e}")
            raise

    def receive_messages(self, max_messages: int = 1, wait_time_seconds: int = 20, visibility_timeout: int = 300) -> List[Dict[str, Any]]:
        """Receive messages from SQS queue"""
        if not self.queue_url:
            return []
        
        try:
            response = self.sqs.receive_message(
                QueueUrl=self.queue_url,
                MaxNumberOfMessages=max_messages,
                WaitTimeSeconds=wait_time_seconds,
                VisibilityTimeout=visibility_timeout
            )
            return response.get("Messages", [])
        except ClientError as e:
            logger.error(f"Error receiving messages from SQS: {e}")
            return []

    def delete_message(self, receipt_handle: str):
        """Delete a message from SQS queue"""
        if not self.queue_url:
            return
        
        try:
            self.sqs.delete_message(
                QueueUrl=self.queue_url,
                ReceiptHandle=receipt_handle
            )
            logger.debug("Deleted message from SQS")
        except ClientError as e:
            logger.error(f"Error deleting message from SQS: {e}")

    def change_message_visibility(self, receipt_handle: str, visibility_timeout: int):
        """Change message visibility timeout"""
        if not self.queue_url:
            return
        
        try:
            self.sqs.change_message_visibility(
                QueueUrl=self.queue_url,
                ReceiptHandle=receipt_handle,
                VisibilityTimeout=visibility_timeout
            )
            logger.debug(f"Changed message visibility to {visibility_timeout}")
        except ClientError as e:
            logger.error(f"Error changing message visibility: {e}")
