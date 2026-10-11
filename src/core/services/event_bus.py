import asyncio
import inspect
from typing import Callable, List, Any
import logging

logger = logging.getLogger(__name__)

class EventBus:
    def __init__(self):
        self._subscribers: dict[str, List[Callable[[Any], None]]] = {}

    def subscribe(self, event_type: str, callback: Callable[[Any], None]):
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(callback)
        logger.info(f"Subscribed to event: {event_type}")

    def _safe_execute(self, callback: Callable[[Any], None], data: Any, event_type: str):
        try:
            callback(data)
        except Exception as e:
            logger.error(f"Error in subscriber callback for {event_type}: {e}", exc_info=True)

    async def _safe_async_execute(self, callback: Callable[[Any], Any], data: Any, event_type: str):
        try:
            await callback(data)
        except Exception as e:
            logger.error(f"Error in async subscriber callback for {event_type}: {e}", exc_info=True)

    def publish(self, event_type: str, data: Any):
        """
        Dispatches event notifications asynchronously without stalling the calling HTTP thread.
        Uses asyncio.create_task to offload callbacks in an asynchronous fire-and-forget pattern.
        """
        if event_type not in self._subscribers:
            return

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        for callback in self._subscribers[event_type]:
            if inspect.iscoroutinefunction(callback):
                if loop and loop.is_running():
                    loop.create_task(self._safe_async_execute(callback, data, event_type))
                else:
                    import threading
                    threading.Thread(
                        target=lambda: asyncio.run(self._safe_async_execute(callback, data, event_type)), 
                        daemon=True
                    ).start()
            else:
                # Synchronous callback: execute in background thread to never stall the HTTP response
                if loop and loop.is_running():
                    loop.create_task(asyncio.to_thread(self._safe_execute, callback, data, event_type))
                else:
                    import threading
                    threading.Thread(
                        target=self._safe_execute, 
                        args=(callback, data, event_type), 
                        daemon=True
                    ).start()

# Global singleton event bus
event_bus = EventBus()

