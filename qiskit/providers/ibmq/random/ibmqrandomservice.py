# -*- coding: utf-8 -*-

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

"""IBMQ random number service."""

import logging
from typing import Dict, List

from qiskit.providers.ibmq import accountprovider  # pylint: disable=unused-import
from .baserandomservice import BaseRandomService
from .cqcextractor import CQCExtractor
from ..api.clients.random import RandomClient
from ..api.exceptions import RequestsApiError
from ..exceptions import IBMQError

logger = logging.getLogger(__name__)


class IBMQRandomService:
    """Random number services for an IBM Quantum Experience account provider.

    Represent a namespace for random number services available to this provider.
    An instance of this class is used as an attribute to the
    :class:`~qiskit.providers.ibmq.AccountProvider` class.
    This allows a convenient way to query for
    all services or to access a specific one::

        random_services = provider.random.services()
        extractor = provider.random.get_extractor('cqc_extractor')
        extractor = provider.random.cqc_extractor  # Short hand for above.
    """

    def __init__(self, provider: 'accountprovider.AccountProvider', access_token: str) -> None:
        """IBMQRandomService constructor.

        Args:
            provider: IBM Quantum Experience account provider.
            access_token: IBM Quantum Experience access token.
        """
        self._provider = provider
        if provider.credentials.extractor_url:
            self._random_client = RandomClient(access_token, provider.credentials)
            self._initialized = False
        else:
            self._random_client = None
            self._initialized = True
        self._services = {}     # type: Dict[str, BaseRandomService]

    def _discover_services(self) -> None:
        """Discovers the remote random services for this provider, if not already known."""
        if not self._initialized:
            try:
                services = self._random_client.list_services()
                for service in services:
                    service_name = service['name']
                    if service_name == 'cqc':
                        service_name = 'cqc_extractor'
                        extractor = CQCExtractor(name=service_name,
                                                 provider=self._provider,
                                                 client=self._random_client,
                                                 methods=service['extractors'])
                        self._services[service_name] = extractor
                    else:
                        logger.warning("Unknown service %s found. It will be ignored.",
                                       service_name)
                self.__dict__.update(self._services)
                self._initialized = True
            except RequestsApiError as err:
                logger.warning("Unable to retrieve service information. "
                               "Please try again later. Error: %s", str(err))
                pass

    def services(self) -> List[BaseRandomService]:
        """Return all random number services available to this account."""
        self._discover_services()
        return list(self._services.values())

    def get_service(self, name: str) -> BaseRandomService:
        """Return the random number service with the given name.

        Args:
            name: Name of the service.

        Returns:
            Service with the given name.

        Raises:
            IBMQError: If the service cannot be found.
        """
        self._discover_services()
        service = self._services.get(name, None)
        if service is None:
            raise IBMQError('No service with the name {} can be found.'.format(name))

        return service

    def __dir__(self):
        self._discover_services()
        return self.__dict__

    def __getattr__(self, item):
        self._discover_services()
        try:
            return self._services[item]
        except KeyError:
            raise AttributeError("'{}' object has no attribute '{}'".format(
                self.__class__.__name__, item))
