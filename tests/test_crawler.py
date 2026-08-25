"""
Unit tests for SSRF-safe HTTP informant crawler.
"""
import pytest
from kingdom_server.core.crawler import SSRFCrawler, SSRFProtectionError

def test_ssrf_blocked_loopback_ips():
    """Verify loopback IPv4 and IPv6 addresses are blocked."""
    assert SSRFCrawler.is_ip_blocked("127.0.0.1") is True
    assert SSRFCrawler.is_ip_blocked("127.0.0.2") is True
    assert SSRFCrawler.is_ip_blocked("::1") is True

def test_ssrf_blocked_rfc1918_ips():
    """Verify RFC 1918 private subnets are blocked."""
    assert SSRFCrawler.is_ip_blocked("10.0.0.1") is True
    assert SSRFCrawler.is_ip_blocked("172.16.0.1") is True
    assert SSRFCrawler.is_ip_blocked("192.168.1.1") is True

def test_ssrf_blocked_cloud_metadata():
    """Verify cloud metadata 169.254.169.254 IP is blocked."""
    assert SSRFCrawler.is_ip_blocked("169.254.169.254") is True
    assert SSRFCrawler.is_ip_blocked("169.254.1.1") is True

def test_ssrf_allowed_public_ips():
    """Verify public internet IPs are allowed."""
    assert SSRFCrawler.is_ip_blocked("8.8.8.8") is False
    assert SSRFCrawler.is_ip_blocked("1.1.1.1") is False

def test_ssrf_validate_url_exceptions():
    """Test validate_url raises SSRFProtectionError on illegal hosts/schemes."""
    with pytest.raises(SSRFProtectionError):
        SSRFCrawler.validate_url("http://127.0.0.1/admin")

    with pytest.raises(SSRFProtectionError):
        SSRFCrawler.validate_url("http://localhost:8080/secret")

    with pytest.raises(SSRFProtectionError):
        SSRFCrawler.validate_url("http://169.254.169.254/latest/meta-data/")

    with pytest.raises(SSRFProtectionError):
        SSRFCrawler.validate_url("ftp://example.com/file")
