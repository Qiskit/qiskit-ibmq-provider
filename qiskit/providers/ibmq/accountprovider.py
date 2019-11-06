# -*- coding: utf-8 -*-

# This code is part of Qiskit.
#
# (C) Copyright IBM 2017, 2019.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Provider for a single IBM Quantum Experience account."""

import logging
from typing import Dict, List, Optional, Any
from collections import OrderedDict

from qiskit.providers import BaseProvider  # type: ignore[attr-defined]
from qiskit.providers.models import (QasmBackendConfiguration,
                                     PulseBackendConfiguration)
from qiskit.validation.exceptions import ModelValidationError

from .api.clients import AccountClient
from .ibmqbackend import IBMQBackend, IBMQSimulator
from .credentials import Credentials
from .ibmqbackendservice import IBMQBackendService


logger = logging.getLogger(__name__)


class AccountProvider(BaseProvider):
    """Provider for a single IBM Quantum Experience account."""

    def __init__(self, credentials: Credentials, access_token: str) -> None:
        """Return a new AccountProvider.

        The ``provider_backends`` attribute can be used to autocomplete
        backend names, by pressing ``tab`` after
        ``AccountProvider.provider_backends.``. Note that this feature may
        not be available if an error occurs during backend discovery.

        Args:
            credentials: IBM Q Experience credentials.
            access_token: access token for IBM Q Experience.
        """
        super().__init__()

        self.credentials = credentials

        # Set the clients.
        self._api = AccountClient(access_token,
                                  credentials.url,
                                  credentials.websockets_url,
                                  use_websockets=(not credentials.proxies),
                                  **credentials.connection_parameters())

        # Initialize the internal list of backends.
        self._backends = self._discover_remote_backends()
        self.backends = IBMQBackendService(self)  # type: ignore[assignment]

    def backends(self, name: Optional[str] = None, **kwargs: Any) -> List[IBMQBackend]:
        # pylint: disable=method-hidden
        # This method is only for faking the subclassing of `BaseProvider`, as
        # `.backends()` is an abstract method. Upon initialization, it is
        # replaced by a `IBMQBackendService` instance.
        pass

    def _discover_remote_backends(self, timeout: Optional[float] = None) -> Dict[str, IBMQBackend]:
        """Return the remote backends available.

        Args:
            timeout: number of seconds to wait for the discovery.

        Returns:
            a dict of the remote backend instances, keyed by backend name.
        """
        ret = OrderedDict()  # type: ignore[var-annotated]
        configs_list = self._api.list_backends(timeout=timeout)
        for raw_config in configs_list:
            # Make sure the raw_config is of proper type
            if not isinstance(raw_config, dict):
                logger.warning("An error occurred when retrieving backend "
                               "information. Some backends might not be available.")
                continue

            try:
                if raw_config.get('open_pulse', False):
                    config = PulseBackendConfiguration.from_dict(raw_config)
                else:
                    config = QasmBackendConfiguration.from_dict(raw_config)
                backend_cls = IBMQSimulator if config.simulator else IBMQBackend
                ret[config.backend_name] = backend_cls(
                    configuration=config,
                    provider=self,
                    credentials=self.credentials,
                    api=self._api)
            except ModelValidationError as ex:
                logger.warning(
                    'Remote backend "%s" could not be instantiated due to an '
                    'invalid config: %s',
                    raw_config.get('backend_name',
                                   raw_config.get('name', 'unknown')),
                    ex)

        return ret

    def __eq__(  # type: ignore[overide]
            self,
            other: 'AccountProvider'
    ) -> bool:
        return self.credentials == other.credentials

    def __repr__(self) -> str:
        credentials_info = "hub='{}', group='{}', project='{}'".format(
            self.credentials.hub, self.credentials.group, self.credentials.project)

        return "<{} for IBMQ({})>".format(
            self.__class__.__name__, credentials_info)
