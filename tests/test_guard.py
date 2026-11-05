import socket

import pytest


def test_network_is_blocked():
    with pytest.raises(RuntimeError, match="network access is blocked"):
        socket.socket().connect(("127.0.0.1", 9))
