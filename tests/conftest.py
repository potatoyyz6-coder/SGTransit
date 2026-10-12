"""Tests use synthetic providers; permit local HTTP tests, never external calls."""
import ipaddress
import socket

import pytest


@pytest.fixture(autouse=True)
def no_external_network_or_real_keys(monkeypatch):
    for name in ("LTA_DATAMALL_API_KEY", "LTA_ACCOUNT_KEY"):
        monkeypatch.delenv(name, raising=False)
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex
    original_getaddrinfo = socket.getaddrinfo

    def local(host):
        if host in (None, "localhost", b"localhost"):
            return
        if isinstance(host, bytes):
            host = host.decode("ascii")
        try:
            if ipaddress.ip_address(host).is_loopback:
                return
        except ValueError:
            pass
        raise AssertionError("External network is forbidden in tests")

    def connect(sock, address):
        local(address[0])
        return original_connect(sock, address)

    def connect_ex(sock, address):
        local(address[0])
        return original_connect_ex(sock, address)

    def getaddrinfo(host, *args, **kwargs):
        local(host)
        return original_getaddrinfo(host, *args, **kwargs)

    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket.socket, "connect_ex", connect_ex)
    monkeypatch.setattr(socket, "getaddrinfo", getaddrinfo)
