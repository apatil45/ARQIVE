"""
Simple in-process queue for Ollama (one inference at a time on CPU).
Max depth 10; 503 if exceeded. Position/ETA for SSE.
"""
from __future__ import annotations

import asyncio
import logging
from collections import deque

logger = logging.getLogger(__name__)

MAX_QUEUE_DEPTH = 10
QUEUE_TIMEOUT = 300  # seconds

_queue: deque[tuple[str, asyncio.Future]] = deque()
_lock = asyncio.Lock()


async def enqueue(request_id: str) -> tuple[int, int] | None:
    """
    Enqueue a request. Returns (position, eta_seconds) if queued, None if accepted immediately.
    Raises Exception (503) if queue full.
    """
    async with _lock:
        if len(_queue) >= MAX_QUEUE_DEPTH:
            raise Exception("Queue full")
        fut: asyncio.Future = asyncio.get_event_loop().create_future()
        _queue.append((request_id, fut))
        pos = len(_queue)
        # Rough ETA: 30s per request ahead
        eta = (pos - 1) * 30 if pos > 1 else 0
        if pos > 1:
            return (pos - 1, eta)
        return None


async def dequeue(request_id: str) -> None:
    """Mark request done; wake next in queue."""
    async with _lock:
        for i, (rid, fut) in enumerate(_queue):
            if rid == request_id:
                _queue.remove((rid, fut))
                try:
                    fut.set_result(None)
                except asyncio.InvalidStateError:
                    pass
                return


async def wait_turn(request_id: str) -> None:
    """Wait until this request is at head and can run. Call dequeue when done."""
    while True:
        async with _lock:
            if _queue and _queue[0][0] == request_id:
                return
            # Find our future
            for rid, fut in _queue:
                if rid == request_id:
                    await asyncio.wait_for(fut, timeout=QUEUE_TIMEOUT)
                    break
        await asyncio.sleep(0.1)
