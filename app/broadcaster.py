"""In-memory registry of SSE clients, one bounded asyncio.Queue each."""
import asyncio

UPDATE = "update"


class Broadcaster:
    def __init__(self, queue_size: int = 16) -> None:
        self._queue_size = queue_size
        self._clients: set[asyncio.Queue[str]] = set()

    @property
    def client_count(self) -> int:
        return len(self._clients)

    def subscribe(self) -> asyncio.Queue[str]:
        queue: asyncio.Queue[str] = asyncio.Queue(maxsize=self._queue_size)
        self._clients.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[str]) -> None:
        self._clients.discard(queue)

    def broadcast(self, message: str = UPDATE) -> int:
        """Queue a message for every client; returns the number of clients.

        Slow-client policy: if a client's queue is full, its oldest pending
        message is dropped to make room. Notifications are generic, so a
        client that missed some still refreshes once on the newest one, and
        memory stays bounded.
        """
        for queue in list(self._clients):
            if queue.full():
                queue.get_nowait()
            queue.put_nowait(message)
        return len(self._clients)
