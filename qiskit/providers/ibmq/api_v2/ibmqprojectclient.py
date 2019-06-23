# -*- coding: utf-8 -*-

# This code is part of Qiskit.
#
# (C) Copyright IBM 2018, 2019.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Client for accessing IBM Q."""

from .ibmqclient import IBMQClient
from .rest import Api
from .session import RetrySession
from .websocket import WebsocketClient


class IBMQProjectClient(IBMQClient):
    """Client for programmatic access to the IBM Q API."""

    def __init__(self, access_token, api_url, websockets_url, **request_kwargs):
        """IBMQClient constructor.

        Args:
            access_token (str):
            api_url (str):
            websockets_url (str):
            **request_kwargs (dict): arguments for the `requests` Session.
        """
        self.client_api = Api(RetrySession(api_url, access_token,
                                           **request_kwargs))
        self.client_ws = WebsocketClient(websockets_url, access_token)
