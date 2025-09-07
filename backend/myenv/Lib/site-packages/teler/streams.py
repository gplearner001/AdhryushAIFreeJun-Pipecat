import asyncio
import contextlib
import logging
from enum import Enum
from typing import Awaitable, Callable, Tuple

import websockets

from teler import exceptions

logger = logging.getLogger(__name__)


class StreamType(Enum):
    UNIDIRECTIONAL = 0
    BIDIRECTIONAL = 1


class StreamOp(Enum):
    RELAY = 0
    PASS = 1
    STOP = 2


StreamHandler = Callable[[str], Awaitable[Tuple[str, StreamOp]]]


class StreamConnector:
    """Media Stream Connector Interface.

    Bridges the call stream to a remote websocket via pluggable handlers.
    """

    @staticmethod
    async def _default_stream_handler(message: str) -> Tuple[str, StreamOp]:
        return (message, StreamOp.RELAY)

    def __init__(
        self,
        stream_type: StreamType = StreamType.BIDIRECTIONAL,
        remote_url: str = "",
        call_stream_handler: StreamHandler = _default_stream_handler,
        remote_stream_handler: StreamHandler = _default_stream_handler,
    ):
        if stream_type == StreamType.UNIDIRECTIONAL:
            raise exceptions.NotImplementedException(
                msg="Unidirectional streams are not supported yet."
            )
        if not remote_url:
            raise exceptions.BadParametersException(
                param="remote_url", msg="remote_url is a required parameter."
            )
        self.stream_type = stream_type
        self.remote_url = remote_url
        self.call_stream_handler = call_stream_handler
        self.remote_stream_handler = remote_stream_handler

    async def bridge_stream(self, call_ws) -> None:
        async with websockets.connect(self.remote_url) as remote_ws:

            logger.info(f"[StreamConnector]: connected to {self.remote_url}")

            async def call_stream() -> None:
                async for message in call_ws.iter_text():
                    logger.debug(
                        f"[StreamConnector]: received message on call stream: {message}"
                    )
                    res = await self.call_stream_handler(message)
                    if not isinstance(res, tuple):
                        raise exceptions.BadParametersException(
                            param="Stream handler response",
                            msg="Stream handler response must be a tuple of (str, StreamOp)",
                        )
                    data, stream_op = res
                    if stream_op == StreamOp.RELAY:
                        await remote_ws.send(data)
                    elif stream_op == StreamOp.STOP:
                        logger.info(
                            f"[StreamConnector]: Received STOP, closing call stream..."
                        )
                        await call_ws.close(
                            code=1000, reason="Stream stopped by client"
                        )
                        break

            async def remote_stream() -> None:
                async for message in remote_ws:
                    logger.debug(
                        f"[StreamConnector]: received message on remote stream: {message}"
                    )
                    res = await self.remote_stream_handler(message)
                    if not isinstance(res, tuple):
                        raise exceptions.BadParametersException(
                            param="Stream handler response",
                            msg="Stream handler response must be a tuple of (str, StreamOp)",
                        )
                    data, stream_op = res
                    if stream_op == StreamOp.RELAY:
                        await call_ws.send_text(data)
                    elif stream_op == StreamOp.STOP:
                        logger.info(
                            f"[StreamConnector]: Received STOP, closing call stream..."
                        )
                        await call_ws.close(
                            code=1000, reason="Stream stopped by client"
                        )
                        break

            done, pending = await asyncio.wait(
                [
                    asyncio.create_task(call_stream()),
                    asyncio.create_task(remote_stream()),
                ],
                return_when=asyncio.FIRST_COMPLETED,
            )
            for t in pending:
                t.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await t

            logger.info("[StreamConnector]: bridge closed")
