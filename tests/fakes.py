import asyncio
import json
from dataclasses import dataclass, field
from typing import Any

from aiohttp import web


@dataclass(frozen=True)
class FakeResponse:
    status: int = 200
    body: str = ""

    @classmethod
    def json(cls, payload: Any, status: int = 200) -> "FakeResponse":
        return cls(status=status, body=json.dumps(payload))


@dataclass
class FakeAPI:
    """Local HTTP API that replies with scripted responses in order.

    The last response is repeated once the others are used up.
    """

    responses: list[FakeResponse] = field(default_factory=list)
    delay: float = 0
    requests: list[tuple[str, dict[str, str]]] = field(default_factory=list)

    @property
    def calls(self) -> int:
        return len(self.requests)

    async def handle(self, request: web.Request) -> web.Response:
        self.requests.append((request.path, dict(request.query)))
        await asyncio.sleep(self.delay)
        if len(self.responses) > 1:
            response = self.responses.pop(0)
        else:
            response = self.responses[0]
        return web.Response(
            status=response.status,
            text=response.body,
            content_type="application/json",
        )
