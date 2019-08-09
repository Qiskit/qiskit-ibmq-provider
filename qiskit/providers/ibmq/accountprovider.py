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
from collections import OrderedDict
from types import SimpleNamespace

from qiskit.providers import BaseProvider
from qiskit.providers.models import (QasmBackendConfiguration,
                                     PulseBackendConfiguration)
from qiskit.providers.providerutils import filter_backends
from qiskit.validation.exceptions import ModelValidationError

from .api_v2.clients import AccountClient
from .api_v2.exceptions import RequestsApiError
from .circuits import CircuitsManager
from .ibmqbackend import IBMQBackend, IBMQSimulator

logger = logging.getLogger(__name__)


class AccountProvider(BaseProvider):
    """Provider for a single IBM Quantum Experience account."""

    def __init__(self, credentials, access_token):
        """Return a new AccountProvider.

        Args:
            credentials (Credentials): IBM Q Experience credentials.
            access_token (str): access token for IBM Q Experience.
        """
        super().__init__()

        self.credentials = credentials

        # Set the clients.
        self._api = AccountClient(access_token,
                                  credentials.url,
                                  credentials.websockets_url,
                                  **credentials.connection_parameters())
        self.circuits = CircuitsManager(self._api)

        # Initialize the internal list of backends, lazy-loading it on first
        # access.
        self._backends = None

        self.provider_backends = ProviderBackends(self)

    def backends(self, name=None, filters=None, timeout=None, **kwargs):
        """Return all backends accessible via this provider, subject to optional filtering.

        Args:
            name (str): backend name to filter by
            filters (callable): more complex filters, such as lambda functions
                e.g. AccountProvider.backends(
                    filters=lambda b: b.configuration['n_qubits'] > 5)
            timeout (float): number of seconds to wait for backend discovery.
            kwargs: simple filters specifying a true/false criteria in the
                backend configuration or backend status or provider credentials
                e.g. AccountProvider.backends(n_qubits=5, operational=True)

        Returns:
            list[IBMQBackend]: list of backends available that match the filter
        """
        # pylint: disable=arguments-differ
        if self._backends is None:
            self._backends = self._discover_remote_backends(timeout=timeout)

        backends = self._backends.values()

        # Special handling of the `name` parameter, to support alias
        # resolution.
        if name:
            aliases = self._aliased_backend_names()
            aliases.update(self._deprecated_backend_names())
            name = aliases.get(name, name)
            kwargs['backend_name'] = name

        return filter_backends(backends, filters=filters, **kwargs)

    def _discover_remote_backends(self, timeout=None):
        """Return the remote backends available.

        Args:
            timeout (float): number of seconds to wait for the discovery.

        Returns:
            dict[str:IBMQBackend]: a dict of the remote backend instances,
                keyed by backend name.
        """
        ret = OrderedDict()
        configs_list = self._api.available_backends(timeout=timeout)
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

    @staticmethod
    def _deprecated_backend_names():
        """Returns deprecated backend names."""
        return {
            'ibmqx_qasm_simulator': 'ibmq_qasm_simulator',
            'ibmqx_hpc_qasm_simulator': 'ibmq_qasm_simulator',
            'real': 'ibmqx1'
            }

    @staticmethod
    def _aliased_backend_names():
        """Returns aliased backend names."""
        return {
            'ibmq_5_yorktown': 'ibmqx2',
            'ibmq_5_tenerife': 'ibmqx4',
            'ibmq_16_rueschlikon': 'ibmqx5',
            'ibmq_20_austin': 'QS1_1'
            }

    def __eq__(self, other):
        return self.credentials == other.credentials

    def __repr__(self):
        credentials_info = "hub='{}', group='{}', project='{}'".format(
            self.credentials.hub, self.credentials.group, self.credentials.project)

        return "<{} for IBMQ({})>".format(
            self.__class__.__name__, credentials_info)


class ProviderBackends(SimpleNamespace):
    """Backend namespace for the provider"""

    def __init__(self, provider):
        """Creates a new ProviderBackends instance.

        Args:
            provider (AccountProvider): IBM Q Experience account provider
        """
        self._provider = provider
        self._initialized = False
        super().__init__()

    def _discover_backends(self):
        """Discovers the remote backends if not already known."""
        if not self._initialized:
            try:
                for backend in self._provider.backends():
                    setattr(self, backend.name(), backend)
                self._initialized = True
            except RequestsApiError:
                # Ignore any networking errors since this is a convenience feature
                pass

    def __dir__(self):
        self._discover_backends()
        return super().__dir__()

    def __getattr__(self, item):
        self._discover_backends()
        return super().__getattribute__(item)
