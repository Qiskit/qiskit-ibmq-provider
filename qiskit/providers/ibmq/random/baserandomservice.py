# This code is part of Qiskit.
#
# (C) Copyright IBM 2020.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Module for interfacing with a remote extractor."""

import logging
from typing import List, Any
from abc import ABC, abstractmethod


from qiskit.providers.ibmq import accountprovider  # pylint: disable=unused-import
from ..api.clients.random import RandomClient

logger = logging.getLogger(__name__)


class BaseRandomService(ABC):
    """Base class for random number services."""

    def __init__(
            self,
            name: str,
            provider: 'accountprovider.AccountProvider',
            client: RandomClient,
            methods: List
    ):
        """BaseRandomService constructor.

        Args:
            name: Name of the extractor.
            provider: IBM Quantum Experience account provider.
            client: Client used to communicate with the server.
            methods: Service methods.
        """
        self.name = name
        self._provider = provider
        self._client = client
        self.methods = methods

    @abstractmethod
    def run(self, *args: Any, **kwargs: Any) -> Any:
        """Execute the service."""
        pass
