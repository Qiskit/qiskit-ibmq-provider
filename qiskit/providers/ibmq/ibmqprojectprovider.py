# -*- coding: utf-8 -*-

# This code is part of Qiskit.
#
# (C) Copyright IBM 2017, 2018.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Provider for a single IBMQ account."""

import logging

from qiskit.providers.ibmq.api_v2 import IBMQProjectClient
from .circuits import CircuitsManager
from .ibmqsingleprovider import IBMQSingleProvider

logger = logging.getLogger(__name__)


class IBMQProjectProvider(IBMQSingleProvider):
    """Provider for single IBMQ accounts.

    Note: this class is not part of the public API and is not guaranteed to be
    present in future releases.
    """

    def __init__(self, credentials, access_token):
        """Return a new IBMQSingleProvider.

        Args:
            credentials (Credentials): IBM Q Experience credentials.
            access_token (str): access token for IBM Q Experience.
        """
        self.credentials = credentials

        self._api = IBMQProjectClient(access_token,
                                      credentials.url,
                                      credentials.websockets_url,
                                      **credentials.connection_parameters())

        # TODO: remove when fully removing IBMQSingleProvider, and adjust
        # the reference in `_discover_remote_backends()`.
        self._ibm_provider = self

        # Populate the list of remote backends.
        self._backends = self._discover_remote_backends()

        # Set circuits manager.
        circuit_client = IBMQProjectClient(access_token,
                                           credentials.base_url,
                                           credentials.websockets_url,
                                           **credentials.connection_parameters())
        self.circuits = CircuitsManager(circuit_client)
