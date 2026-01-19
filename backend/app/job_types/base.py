from abc import ABC, abstractmethod
from typing import AsyncIterator, Dict, Any
import logging

logger = logging.getLogger(__name__)


class JobProcessor(ABC):
    """Base class for all job processors"""
    
    def __init__(self, job: Dict[str, Any]):
        self.job = job
        self.result: Dict[str, Any] = {}
    
    @abstractmethod
    async def process(self) -> AsyncIterator[Dict[str, Any]]:
        """
        Process the job and yield progress updates.
        Each yield should be a dict with: progress, status, message, data
        """
        pass
    
    def get_result(self) -> Dict[str, Any]:
        """Get the final result of the job"""
        return self.result
