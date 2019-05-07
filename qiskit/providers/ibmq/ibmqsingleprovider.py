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
from collections import OrderedDict

from qiskit.providers import BaseProvider
from qiskit.providers.models import (QasmBackendConfiguration,
                                     PulseBackendConfiguration)
from qiskit.providers.providerutils import filter_backends
from qiskit.validation.exceptions import ModelValidationError

from .api import IBMQConnector
from .api_v2 import IBMQClient
from .ibmqbackend import IBMQBackend, IBMQSimulator


logger = logging.getLogger(__name__)


class IBMQSingleProvider(BaseProvider):
    """Provider for single IBMQ accounts.

    Note: this class is not part of the public API and is not guaranteed to be
    present in future releases.
    """

    def __init__(self, credentials, ibmq_provider):
        """Return a new IBMQSingleProvider.

        Args:
            credentials (Credentials): Quantum Experience or IBMQ credentials.
            ibmq_provider (IBMQProvider): IBMQ main provider.
        """
        super().__init__()

        # Get a connection to IBMQ.
        self.credentials = credentials
        self._api = self._authenticate(self.credentials)
        self._ibm_provider = ibmq_provider

        # Populate the list of remote backends.
        self._backends = self._discover_remote_backends()

    def backends(self, name=None, filters=None, **kwargs):
        # pylint: disable=arguments-differ
        backends = self._backends.values()

        if name:
            kwargs['backend_name'] = name

        return filter_backends(backends, filters=filters, **kwargs)

    @classmethod
    def _authenticate(cls, credentials):
        """Authenticate against the IBMQ API.

        Args:
            credentials (Credentials): Quantum Experience or IBMQ credentials.

        Returns:
            IBMQConnector: instance of the IBMQConnector.
        Raises:
            ConnectionError: if the authentication resulted in error.
        """
        # TODO: add more robust detection.
        # Check if the URL belongs to auth services of the new API.
        if ('quantum-computing.ibm.com/api' in credentials.url and
                'auth' in credentials.url):
            return IBMQClient(api_token=credentials.token,
                              auth_url=credentials.url)

        try:
            config_dict = {
                'url': credentials.url,
            }
            if credentials.proxies:
                config_dict['proxies'] = credentials.proxies
            if credentials.websocket_url:
                config_dict['websocket_url'] = credentials.websocket_url
            return IBMQConnector(credentials.token, config_dict,
                                 credentials.verify)
        except Exception as ex:
            root_exception = ex
            if 'License required' in str(ex):
                # For the 401 License required exception from the API, be
                # less verbose with the exceptions.
                root_exception = None
            raise ConnectionError("Couldn't connect to IBMQ server: {0}"
                                  .format(ex)) from root_exception

    def _discover_remote_backends(self):
        """Return the remote backends available.

        Returns:
            dict[str:IBMQBackend]: a dict of the remote backend instances,
                keyed by backend name.
        """
        ret = OrderedDict()
        configs_list = self._api.available_backends()
        for raw_config in configs_list:
            try:
                if raw_config.get('open_pulse', False):
                    config = PulseBackendConfiguration.from_dict(raw_config)
                else:
                    config = QasmBackendConfiguration.from_dict(raw_config)
                backend_cls = IBMQSimulator if config.simulator else IBMQBackend
                ret[config.backend_name] = backend_cls(
                    configuration=config,
                    provider=self._ibm_provider,
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

    def __eq__(self, other):
        return self.credentials == other.credentials
