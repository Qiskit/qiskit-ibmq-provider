# This code is part of Qiskit.
#
# (C) Copyright IBM 2021.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Utilities for working with IBM Quantum API."""

from typing import Dict
from urllib.parse import urlparse

from ...credentials import Credentials


def ws_proxy_params(credentials: Credentials, ws_url: str) -> Dict:
    """Extract proxy information for websocket.

    Args:
        credentials: Account credentials.
        ws_url: Websocket URL.

    Returns:
        Proxy information to be used by the websocket client.
    """
    conn_data = credentials.connection_parameters()
    out = {}

    if "proxies" in conn_data:
        proxies = conn_data['proxies']
        url_parts = urlparse(ws_url)
        proxy_keys = [
            ws_url,
            'wss',
            'https://' + url_parts.hostname,
            'https',
            'all://' + url_parts.hostname,
            'all'
        ]
        for key in proxy_keys:
            if key in proxies:
                proxy_parts = urlparse(proxies[key], scheme="http")
                out['http_proxy_host'] = proxy_parts.hostname
                out['http_proxy_port'] = proxy_parts.port
                out['proxy_type'] = \
                    "http" if proxy_parts.scheme.startswith("http") else proxy_parts.scheme
                if proxy_parts.username and proxy_parts.password:
                    out['http_proxy_auth'] = (proxy_parts.username, proxy_parts.password)
                break

    if "auth" in conn_data:
        out['http_proxy_auth'] = (credentials.proxies['username_ntlm'],
                                  credentials.proxies['password_ntlm'])

    return out
