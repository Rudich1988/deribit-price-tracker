from enum import IntEnum


class DeribitErrorCode(IntEnum):
    """Deribit-specific JSON-RPC error codes the client reacts to."""

    TOO_MANY_REQUESTS = 10028
