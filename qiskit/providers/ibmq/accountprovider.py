# This code is part of Qiskit.
#
# (C) Copyright IBM 2017, 2021.
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
from typing import Dict, List, Optional, Any, Callable
from collections import OrderedDict
import traceback

from qiskit.providers import ProviderV1 as Provider  # type: ignore[attr-defined]
from qiskit.providers.models import (QasmBackendConfiguration,
                                     PulseBackendConfiguration)

from .api.clients import AccountClient
from .ibmqbackend import IBMQBackend, IBMQSimulator
from .credentials import Credentials
from .ibmqbackendservice import IBMQBackendService, IBMQDeprecatedBackendService
from .utils.json_decoder import decode_backend_configuration
from .random.ibmqrandomservice import IBMQRandomService
from .experiment.experimentservice import ExperimentService
from .exceptions import IBMQNotAuthorizedError, IBMQInputValueError

logger = logging.getLogger(__name__)


class AccountProvider(Provider):
    """Provider for a single IBM Quantum Experience account.

    The account provider class provides access to the IBM Quantum Experience
    services available to this account.

    You can access a provider by enabling an account with the
    :meth:`IBMQ.enable_account()<IBMQFactory.enable_account>` method, which
    returns the default provider you have access to::

        from qiskit import IBMQ
        provider = IBMQ.enable_account(<INSERT_IBM_QUANTUM_EXPERIENCE_TOKEN>)

    To select a different provider, use the
    :meth:`IBMQ.get_provider()<IBMQFactory.get_provider>` method and specify the hub,
    group, or project name of the desired provider.

    Each provider may offer different services. The main service,
    :class:`~qiskit.providers.ibmq.ibmqbackendservice.IBMQBackendService`, is
    available to all providers and gives access to IBM Quantum Experience
    devices and simulators.

    You can obtain an instance of a service using the :meth:`service()` method
    or as an attribute of this ``AccountProvider`` instance. For example::

        backend_service = provider.service('backend')
        backend_service = provider.service.backend

    Since :class:`~qiskit.providers.ibmq.ibmqbackendservice.IBMQBackendService`
    is the main service, some of the backend-related methods are available
    through this class for convenience.

    The :meth:`backends()` method returns all the backends available to this account::

        backends = provider.backends()

    The :meth:`get_backend()` method returns a backend that matches the filters
    passed as argument. An example of retrieving a backend that matches a
    specified name::

        simulator_backend = provider.get_backend('ibmq_qasm_simulator')

    It is also possible to use the ``backend`` attribute to reference a backend.
    As an example, to retrieve the same backend from the example above::

        simulator_backend = provider.backend.ibmq_qasm_simulator

    Note:
        The ``backend`` attribute can be used to autocomplete the names of
        backends available to this provider. To autocomplete, press ``tab``
        after ``provider.backend.``. This feature may not be available
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
        self._api_client = AccountClient(access_token,
                                         credentials,
                                         **credentials.connection_parameters())

        # Initialize the internal list of backends.
        self._backends = self._discover_remote_backends()
        self._backend = IBMQBackendService(self)
        self.backends = IBMQDeprecatedBackendService(self.backend)  # type: ignore[assignment]

        # Initialize other services.
        self._random = IBMQRandomService(self, access_token) \
            if credentials.extractor_url else None
        self._experiment = ExperimentService(self, access_token) \
            if credentials.experiment_url else None

        self._services = {'backend': self._backend,
                          'random': self._random,
                          'experiment': self._experiment}

    def backends(
            self,
            name: Optional[str] = None,
            filters: Optional[Callable[[List[IBMQBackend]], bool]] = None,
            **kwargs: Any
    ) -> List[IBMQBackend]:
        """Return all backends accessible via this provider, subject to optional filtering.

        Args:
            name: Backend name to filter by.
            filters: More complex filters, such as lambda functions.
                For example::

                    AccountProvider.backends(filters=lambda b: b.configuration().n_qubits > 5)
            kwargs: Simple filters that specify a ``True``/``False`` criteria in the
                backend configuration, backends status, or provider credentials.
                An example to get the operational backends with 5 qubits::

                    AccountProvider.backends(n_qubits=5, operational=True)

        Returns:
            The list of available backends that match the filter.
        """
        # pylint: disable=method-hidden
        # pylint: disable=arguments-differ
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
        configs_list = self._api_client.list_backends(timeout=timeout)
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
                    api_client=self._api_client)
            except Exception:  # pylint: disable=broad-except
                logger.warning(
                    'Remote backend "%s" for provider %s could not be instantiated due to an '
                    'invalid config: %s',
                    raw_config.get('backend_name', raw_config.get('name', 'unknown')),
                    repr(self), traceback.format_exc())

        return ret

    def service(self, name: str) -> Any:
        """Return the specified service.

        Args:
            name: Name of the service.

        Returns:
            The specified service.

        Raises:
            IBMQInputValueError: If an unknown service name is specified.
            IBMQNotAuthorizedError: If the account is not authorized to use
                the service.
        """
        if name not in self._services:
            raise IBMQInputValueError(f"Unknown service {name} specified.")

        if self._services[name] is None:
            raise IBMQNotAuthorizedError("You are not authorized to use this service.")

        return self._services[name]

    def services(self) -> Dict:
        """Return all available services.

        Returns:
            All services available to this provider.
        """
        return {key: val for key, val in self._services.items() if val is not None}

    @property
    def backend(self) -> IBMQBackendService:
        """Return the backend service.

        Returns:
            The backend service instance.
        """
        return self._backend

    @property
    def experiment(self) -> ExperimentService:
        """Return the experiment service.

        Returns:
            The experiment service instance.

        Raises:
            IBMQNotAuthorizedError: If the account is not authorized to use
                the experiment service.
        """
        if self._experiment:
            return self._experiment
        else:
            raise IBMQNotAuthorizedError("You are not authorized to use the experiment service.")

    @property
    def random(self) -> IBMQRandomService:
        """Return the random number service.

        Returns:
            The random number service instance.

        Raises:
            IBMQNotAuthorizedError: If the account is not authorized to use
                the service.
        """
        if self._random:
            return self._random
        else:
            raise IBMQNotAuthorizedError("You are not authorized to use the random number service.")

    def __eq__(
            self,
            other: Any
    ) -> bool:
        if not isinstance(other, AccountProvider):
            return False
        return self.credentials == other.credentials

    def __repr__(self) -> str:
        credentials_info = "hub='{}', group='{}', project='{}'".format(
            self.credentials.hub, self.credentials.group, self.credentials.project)

        return "<{} for IBMQ({})>".format(
            self.__class__.__name__, credentials_info)
