import os
import json
import logging
from typing import Dict, Any, Optional
import redis.asyncio as redis

logger = logging.getLogger(__name__)


class RedisService:
    def __init__(self):
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self.redis_client = redis.from_url(redis_url, decode_responses=True)
        logger.info(f"Connected to Redis at {redis_url}")

    async def publish_job_update(self, job_id: str, update: Dict[str, Any]):
        """Publish job progress update to Redis channel"""
        channel = f"job:{job_id}"
        try:
            await self.redis_client.publish(channel, json.dumps(update))
            logger.debug(f"Published update to channel {channel}")
        except Exception as e:
            logger.error(f"Error publishing to Redis: {e}")

    async def subscribe_to_job(self, job_id: str):
        """Subscribe to job updates channel"""
        channel = f"job:{job_id}"
        pubsub = self.redis_client.pubsub()
        await pubsub.subscribe(channel)
        return pubsub

    async def close(self):
        """Close Redis connection"""
        await self.redis_client.close()
