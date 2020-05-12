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

from .api.clients import AccountClient
from .ibmqbackend import IBMQBackend, IBMQSimulator
from .credentials import Credentials
from .ibmqbackendservice import IBMQBackendService
from .utils.json_decoder import decode_backend_configuration

logger = logging.getLogger(__name__)


class AccountProvider(BaseProvider):
    """Provider for a single IBM Quantum Experience account.

    The account provider class provides access to the IBM Quantum Experience
    backends available to this account.

    You can access a provider by enabling an account with the
    :meth:`IBMQ.enable_account()<IBMQFactory.enable_account>` method, which
    returns the default provider you have access to::

        from qiskit import IBMQ
        provider = IBMQ.enable_account(<INSERT_IBM_QUANTUM_EXPERIENCE_TOKEN>)

    To select a different provider, use the
    :meth:`IBMQ.get_provider()<IBMQFactory.get_provider>` method and specify the hub,
    group, or project name of the desired provider.

    The :meth:`backends()` method returns all the backends available to this account::

        backends = provider.backends()

    The :meth:`get_backend()` method returns a backend that matches the filters
    passed as argument. An example of retrieving a backend that matches a
    specified name::

        simulator_backend = provider.get_backend('ibmq_qasm_simulator')

    It is also possible to use the ``backends`` attribute to reference a backend.
    As an example, to retrieve the same backend from the example above::

        simulator_backend = provider.backends.ibmq_qasm_simulator

    Note:
        The ``backends`` attribute can be used to autocomplete the names of
        backends available to this provider. To autocomplete, press ``tab``
        after ``provider.backends.``. This feature may not be available
        if an error occurs during backend discovery. Also note that
        this feature is only available in interactive sessions, such as
        in Jupyter Notebook and the Python interpreter.
    """

    def __init__(self, credentials: Credentials, access_token: str) -> None:
        """AccountProvider constructor.

        Args:
            credentials: IBM Quantum Experience credentials.
            access_token: IBM Quantum Experience access token.
        """
        super().__init__()

        self.credentials = credentials
        # set the client.
        self._api = AccountClient(access_token,
                                  credentials.url,
                                  credentials.websockets_url,
                                  use_websockets=(not credentials.proxies),
                                  **credentials.connection_parameters())

        # Initialize the internal list of backends.
        self._backends = self._discover_remote_backends()
        self.backends = IBMQBackendService(self)  # type: ignore[assignment]

    def backends(self, name: Optional[str] = None, **kwargs: Any) -> List[IBMQBackend]:
        """Return all backends accessible via this provider, subject to optional filtering."""
        # pylint: disable=method-hidden
        # This method is only for faking the subclassing of `BaseProvider`, as
        # `.backends()` is an abstract method. Upon initialization, it is
        # replaced by a `IBMQBackendService` instance.
        pass

    def _discover_remote_backends(self, timeout: Optional[float] = None) -> Dict[str, IBMQBackend]:
        """Return the remote backends available for this provider.

        Args:
            timeout: Maximum number of seconds to wait for the discovery of
                remote backends.

        Returns:
            A dict of the remote backend instances, keyed by backend name.
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
                decode_backend_configuration(raw_config)
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
            except TypeError as ex:
                logger.warning(
                    'Remote backend "%s" could not be instantiated due to an '
                    'invalid config: %s',
                    raw_config.get('backend_name',
                                   raw_config.get('name', 'unknown')),
                    ex)

        return ret

    def __eq__(  # type: ignore[override]
            self,
            other: 'AccountProvider'
    ) -> bool:
        return self.credentials == other.credentials

    def __repr__(self) -> str:
        credentials_info = "hub='{}', group='{}', project='{}'".format(
            self.credentials.hub, self.credentials.group, self.credentials.project)

        return "<{} for IBMQ({})>".format(
            self.__class__.__name__, credentials_info)
