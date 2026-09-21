"""
Async SSRF-Safe HTTP Informant Crawler module.
Strictly blocks loopback (127.0.0.1, ::1), RFC 1918 private subnets, and cloud metadata (169.254.169.254).
"""
import ipaddress
import socket
import urllib.parse
from typing import Optional, Dict, Any
import httpx
import logging

logger = logging.getLogger("kingdom.crawler")

class SSRFProtectionError(PermissionError):
    """Exception raised when an SSRF attempt to a restricted IP address or hostname is blocked."""
    pass

class SSRFCrawler:
    """SSRF-Safe Async HTTP Client."""

    BLOCKED_NETWORKS = [
        ipaddress.ip_network("127.0.0.0/8"),          # IPv4 Loopback
        ipaddress.ip_network("10.0.0.0/8"),           # RFC 1918 Private
        ipaddress.ip_network("172.16.0.0/12"),        # RFC 1918 Private
        ipaddress.ip_network("192.168.0.0/16"),       # RFC 1918 Private
        ipaddress.ip_network("169.254.0.0/16"),       # Link-Local & Cloud Metadata (169.254.169.254)
        ipaddress.ip_network("0.0.0.0/8"),            # Current network
        ipaddress.ip_network("224.0.0.0/4"),          # Multicast
        ipaddress.ip_network("240.0.0.0/4"),          # Reserved
        ipaddress.ip_network("::1/128"),              # IPv6 Loopback
        ipaddress.ip_network("fc00::/7"),             # IPv6 Unique Local Address
        ipaddress.ip_network("fe80::/10"),            # IPv6 Link-Local
    ]

    @classmethod
    def is_ip_blocked(cls, ip_str: str) -> bool:
        try:
            ip = ipaddress.ip_address(ip_str)
            for net in cls.BLOCKED_NETWORKS:
                if ip in net:
                    return True
            return False
        except ValueError:
            return True  # Block invalid IP strings

    @classmethod
    def validate_url(cls, url: str) -> str:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in ("http", "https"):
            raise SSRFProtectionError(f"Unsupported scheme '{parsed.scheme}'. Only http and https are allowed.")

        hostname = parsed.hostname
        if not hostname:
            raise SSRFProtectionError("Invalid URL: missing hostname.")

        # Check explicit loopback / localhost hostnames
        if hostname.lower() in ("localhost", "loopback", "127.0.0.1", "::1"):
            raise SSRFProtectionError(f"Access to localhost/loopback ('{hostname}') is blocked by SSRF policy.")

        # Resolve DNS to IP addresses and check all resolved IPs
        try:
            addr_info = socket.getaddrinfo(hostname, None)
            resolved_ips = set(info[4][0] for info in addr_info)
            for ip in resolved_ips:
                if cls.is_ip_blocked(ip):
                    raise SSRFProtectionError(f"URL '{url}' resolves to blocked private/metadata IP '{ip}'.")
        except socket.gaierror as e:
            raise SSRFProtectionError(f"Failed to resolve domain '{hostname}': {e}")

        return url

    @classmethod
    async def fetch(cls, url: str, timeout: float = 10.0, headers: Optional[dict] = None) -> Dict[str, Any]:
        """Validates URL and safely fetches content asynchronously."""
        clean_url = cls.validate_url(url)
        
        async with httpx.AsyncClient(follow_redirects=False, timeout=timeout) as client:
            response = await client.get(clean_url, headers=headers)
            
            # Check redirect target if any
            if response.is_redirect and "location" in response.headers:
                redirect_url = urllib.parse.urljoin(clean_url, response.headers["location"])
                cls.validate_url(redirect_url)  # Validate redirect destination against SSRF rules

            return {
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "text": response.text,
                "url": str(response.url),
            }
