"""Local async message queue used by coordination experiments.

The orchestrator's current hot path does not depend on message passing between
distributed workers. This queue remains as local scaffolding for coordination
experiments and compatibility with the broader architecture shape.
"""

import asyncio
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any
from uuid import uuid4


class MessageType(StrEnum):
    """Types of messages that can be sent through the message bus."""

    TASK = "task"
    RESULT = "result"
    STATUS = "status"
    REFLECTION = "reflection"
    ERROR = "error"


@dataclass
class Message:
    """A message sent through the message bus.

    Attributes:
        id: Unique message identifier.
        type: Type of message (task, result, status, reflection, error).
        sender_id: ID of the agent that sent the message.
        recipient_id: ID of the intended recipient (None for broadcast).
        content: Message content.
        timestamp: Unix timestamp when message was created.
        metadata: Optional additional metadata.
    """

    id: str = field(default_factory=lambda: str(uuid4()))
    type: MessageType = MessageType.TASK
    sender_id: str = "orchestrator"
    recipient_id: str | None = None
    content: Any = None
    timestamp: float = field(default_factory=asyncio.get_event_loop().time)
    metadata: dict[str, Any] = field(default_factory=dict)


class LocalMessageBus:
    """Local async queue for coordination experiments.

    It supports directed and broadcast messages inside one Python process. The
    current research workflow does not rely on it to execute research tasks.

    Example:
        >>> bus = LocalMessageBus()
        >>> # Send a task to researcher-1
        >>> await bus.send(Message(
        ...     type=MessageType.TASK,
        ...     recipient_id="researcher-1",
        ...     content={"query": "example"}
        ... ))
        >>> # Receive results from any agent
        >>> result = await bus.receive(timeout=30.0)
    """

    def __init__(self) -> None:
        """Initialize the message bus."""
        self._queue: asyncio.Queue[Message] = asyncio.Queue()
        self._messages_by_recipient: dict[str, list[Message]] = {}
        self._lock: asyncio.Lock = asyncio.Lock()
        self._active = True

    @property
    def is_active(self) -> bool:
        """Check if the message bus is active.

        Returns:
            True if active, False otherwise.
        """
        return self._active

    async def send(self, message: Message) -> None:
        """Send a message through the bus.

        Args:
            message: The message to send.

        Raises:
            RuntimeError: If the message bus is not active.
        """
        if not self._active:
            msg = "Cannot send message: message bus is not active"
            raise RuntimeError(msg)

        # Add to general queue
        await self._queue.put(message)

        # Add to recipient-specific queue for targeted receive
        if message.recipient_id:
            async with self._lock:
                if message.recipient_id not in self._messages_by_recipient:
                    self._messages_by_recipient[message.recipient_id] = []
                self._messages_by_recipient[message.recipient_id].append(message)

    async def receive(
        self,
        recipient_id: str | None = None,
        timeout: float | None = None,
    ) -> Message:
        """Receive a message from the bus.

        Args:
            recipient_id: Optional recipient ID to filter messages.
                         If None, receives from the general queue.
            timeout: Optional timeout in seconds. If None, waits indefinitely.

        Returns:
            The received message.

        Raises:
            asyncio.TimeoutError: If timeout is exceeded.
            RuntimeError: If the message bus is not active.
        """
        if not self._active:
            msg = "Cannot receive message: message bus is not active"
            raise RuntimeError(msg)

        if recipient_id:
            # Receive from recipient-specific queue
            while self._active:
                async with self._lock:
                    messages = self._messages_by_recipient.get(recipient_id, [])
                    if messages:
                        return messages.pop(0)

                # Wait a bit and check again
                try:
                    return await asyncio.wait_for(
                        self._queue.get(),
                        timeout=timeout,
                    )
                except TimeoutError:
                    if timeout is not None:
                        raise
                    # Continue waiting if no timeout

            msg = "Cannot receive message: message bus is not active"
            raise RuntimeError(msg)
        else:
            # Receive from general queue
            return await asyncio.wait_for(self._queue.get(), timeout=timeout)

    async def receive_all(
        self,
        recipient_id: str | None = None,
        timeout: float | None = None,
    ) -> list[Message]:
        """Receive all available messages.

        Args:
            recipient_id: Optional recipient ID to filter messages.
            timeout: Timeout for initial wait.

        Returns:
            List of all available messages.
        """
        messages: list[Message] = []

        try:
            # Get first message
            first_msg = await self.receive(recipient_id, timeout=timeout)
            messages.append(first_msg)

            # Get any remaining messages without timeout
            if recipient_id:
                async with self._lock:
                    remaining = self._messages_by_recipient.get(recipient_id, [])
                    messages.extend(remaining)
                    self._messages_by_recipient[recipient_id] = []
            else:
                while not self._queue.empty():
                    try:
                        msg = self._queue.get_nowait()
                        messages.append(msg)
                    except asyncio.QueueEmpty:
                        break

        except TimeoutError:
            pass  # No messages available

        return messages

    async def broadcast(self, message_type: MessageType, content: Any) -> None:
        """Broadcast a message to all recipients.

        Args:
            message_type: Type of message to broadcast.
            content: Content of the message.
        """
        message = Message(
            type=message_type,
            recipient_id=None,  # Broadcast to all
            content=content,
        )
        await self.send(message)

    async def shutdown(self) -> None:
        """Shutdown the message bus.

        Prevents sending new messages and drains any pending messages.
        """
        self._active = False

        # Clear any pending messages
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:
                break

        # Clear recipient queues
        async with self._lock:
            self._messages_by_recipient.clear()

    def size(self) -> int:
        """Get the current size of the message queue.

        Returns:
            Number of messages in the queue.
        """
        return self._queue.qsize()

__all__ = [
    "MessageType",
    "Message",
    "LocalMessageBus",
]
