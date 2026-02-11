"""MCP tools for Plex system operations."""

from typing import Any, Dict

from server.client import PlexClient


async def get_server_info(client: PlexClient) -> Dict[str, Any]:
    """Get Plex server information.

    Args:
        client: PlexClient instance

    Returns:
        Dictionary with server info:
        - name: Server friendly name
        - version: Server version
        - platform: Server platform
        - machineIdentifier: Unique machine ID

    Raises:
        plexapi.exceptions.Unauthorized: If authentication fails
        Exception: On connection errors

    Example:
        >>> info = await get_server_info(client)
        >>> print(info["name"])
        My Plex Server
    """
    return await client.get_server_info()
