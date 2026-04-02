"""LBRY JSON-RPC client for local daemon or Odysee public proxy."""

import json
import logging
from typing import Any, Dict, List, Optional

try:
    import requests
except ImportError:
    raise ImportError("requests is required. Install with: pip install requests")


logger = logging.getLogger(__name__)


class LbryClientError(Exception):
    """Raised when LBRY daemon communication fails."""

    pass


class LbryClient:
    """JSON-RPC client for lbrynet daemon or Odysee's public proxy."""

    ODYSEE_PROXY_URL = "https://api.na-backend.odysee.com/api/v1/proxy"

    def __init__(
        self,
        api_url: str = "http://127.0.0.1:5279",
        timeout: int = 60,
        backend_name: str = "LBRY daemon",
        supports_file_ops: bool = True,
    ):
        self.api_url = api_url
        self.timeout = timeout
        self.backend_name = backend_name
        self.supports_file_ops = supports_file_ops
        self.session = requests.Session()

    @classmethod
    def create_odysee_proxy(cls, timeout: int = 60) -> "LbryClient":
        """Create a client backed by Odysee's public JSON-RPC proxy."""
        return cls(
            api_url=cls.ODYSEE_PROXY_URL,
            timeout=timeout,
            backend_name="Odysee public proxy",
            supports_file_ops=False,
        )

    def _call(self, method: str, **params) -> Dict[str, Any]:
        """
        Make a JSON-RPC call to the daemon.

        Args:
            method: The daemon method to call.
            **params: Parameters for the method.

        Returns:
            The result field from the JSON-RPC response.

        Raises:
            LbryClientError: If the call fails or returns an error.
        """
        payload = {"jsonrpc": "2.0", "method": method, "params": params, "id": 1}

        try:
            response = self.session.post(
                self.api_url, json=payload, timeout=self.timeout
            )
            response.raise_for_status()
        except requests.exceptions.ConnectionError as e:
            raise LbryClientError(
                f"Could not connect to {self.backend_name} at {self.api_url}. "
                f"Error: {e}"
            )
        except requests.exceptions.Timeout:
            raise LbryClientError(
                f"Request to {self.backend_name} timed out after {self.timeout} seconds"
            )
        except requests.exceptions.RequestException as e:
            raise LbryClientError(f"Request to {self.backend_name} failed: {e}")

        try:
            data = response.json()
        except json.JSONDecodeError as e:
            raise LbryClientError(f"Invalid JSON response from daemon: {e}")

        if "error" in data and data["error"]:
            error = data["error"]
            raise LbryClientError(
                f"{self.backend_name} returned error: {error.get('message', error)}"
            )

        return data.get("result", {})

    def status(self) -> Dict[str, Any]:
        """
        Check daemon status.

        Returns:
            Status information from the daemon.

        Raises:
            LbryClientError: If the daemon is unreachable.
        """
        return self._call("status")

    def resolve(self, urls: List[str]) -> Dict[str, Any]:
        """
        Resolve URLs to claim metadata.

        Args:
            urls: List of URLs or URIs to resolve.

        Returns:
            Dictionary mapping URLs to their resolved claim data.
        """
        if isinstance(urls, str):
            urls = [urls]

        result = self._call("resolve", urls=urls)
        return result

    def claim_search(
        self,
        channel_claim_id: Optional[str] = None,
        claim_type: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Search for claims.

        Args:
            channel_claim_id: Filter by channel claim ID.
            claim_type: Filter by claim type (e.g., 'stream').
            page: Page number (1-indexed).
            page_size: Number of results per page.
            **kwargs: Additional search parameters.

        Returns:
            Search results containing claims and pagination info.
        """
        params: Dict[str, Any] = {
            "page": page,
            "page_size": page_size,
        }

        if channel_claim_id:
            params["channel_ids"] = [channel_claim_id]

        if claim_type:
            params["claim_type"] = claim_type

        params.update(kwargs)

        return self._call("claim_search", **params)

    def get_channel_claims(
        self,
        channel_claim_id: str,
        page: int = 1,
        page_size: int = 50,
        include_reposts: bool = False,
    ) -> Dict[str, Any]:
        """
        Get all claims published by a channel.

        Args:
            channel_claim_id: The channel's claim ID.
            page: Page number.
            page_size: Number of results per page.
            include_reposts: Whether to include reposts.

        Returns:
            Claims published by the channel.
        """
        params = {
            "channel_ids": [channel_claim_id],
            "claim_type": ["stream", "repost"],
            "page": page,
            "page_size": page_size,
            "order_by": ["release_time"],
        }

        if not include_reposts:
            params["claim_type"] = ["stream"]

        return self._call("claim_search", **params)

    def find_controlling_channel(self, channel_name: str) -> Optional[Dict[str, Any]]:
        """
        Find the controlling channel claim for a channel name.

        This is needed for Odysee's public proxy because user-friendly channel
        URLs can resolve to non-controlling channel claims that do not enumerate
        stream uploads correctly.
        """
        result = self.claim_search(
            name=channel_name,
            claim_type=["channel"],
            is_controlling=True,
            order_by=["effective_amount"],
            page=1,
            page_size=1,
        )
        items = result.get("items", [])
        return items[0] if items else None

    def get(
        self, uri: str, download_directory: Optional[str] = None, **kwargs
    ) -> Dict[str, Any]:
        """
        Download a claim.

        Args:
            uri: The LBRY URI to download.
            download_directory: Directory to save the file.
            **kwargs: Additional download parameters.

        Returns:
            Download result containing file info.
        """
        params = {"uri": uri}

        if download_directory:
            params["download_directory"] = download_directory

        params.update(kwargs)

        return self._call("get", **params)

    def file_list(self, claim_id: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """
        List files managed by the daemon.

        Args:
            claim_id: Filter by claim ID.
            **kwargs: Additional filter parameters.

        Returns:
            List of file information.
        """
        params = {}

        if claim_id:
            params["claim_id"] = claim_id

        params.update(kwargs)

        return self._call("file_list", **params)

    def file_delete(self, claim_id: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """
        Delete a file managed by the daemon.

        Args:
            claim_id: The claim ID of the file to delete.
            **kwargs: Additional parameters.

        Returns:
            Result from the daemon.
        """
        params: Dict[str, Any] = {}

        if claim_id:
            params["claim_id"] = claim_id

        params.update(kwargs)

        return self._call("file_delete", **params)

    def version(self) -> Dict[str, Any]:
        """
        Get daemon version info.

        Returns:
            Version information.
        """
        return self._call("version")


def check_daemon_health(client: LbryClient) -> bool:
    """
    Check if the daemon is running and accessible.

    Args:
        client: LbryClient instance.

    Returns:
        True if daemon is healthy.

    Raises:
        LbryClientError: If daemon is not accessible.
    """
    try:
        status = client.status()
        logger.debug(f"Daemon status: {status}")
        return True
    except LbryClientError:
        raise
