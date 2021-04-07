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
from typing import Dict, List, Optional, Any, Callable, Union
from collections import OrderedDict
import traceback

from qiskit.providers import ProviderV1 as Provider  # type: ignore[attr-defined]
from qiskit.providers.models import (QasmBackendConfiguration,
                                     PulseBackendConfiguration)
from qiskit.circuit import QuantumCircuit, Parameter
from qiskit.pulse.instruction_schedule_map import InstructionScheduleMap
from qiskit.pulse.channels import PulseChannel
from qiskit.providers.backend import BackendV1 as Backend
from qiskit.providers.basebackend import BaseBackend
from qiskit.transpiler import Layout
from qiskit.qobj.utils import MeasLevel, MeasReturnType
from qiskit.exceptions import QiskitError

from .api.clients import AccountClient
from .ibmqbackend import IBMQBackend, IBMQSimulator
from .credentials import Credentials
from .ibmqbackendservice import IBMQBackendService, IBMQDeprecatedBackendService
from .utils.json_decoder import decode_backend_configuration
from .random.ibmqrandomservice import IBMQRandomService
from .experiment.experimentservice import ExperimentService
from .runtime.ibm_runtime_service import IBMRuntimeService
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
        self._runtime = IBMRuntimeService(self, access_token)

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

    def run_circuits(
            self,
            circuits: Union[QuantumCircuit, List[QuantumCircuit]],
            backend: Optional[Union[Backend, BaseBackend]] = None,
            initial_layout: Optional[Union[Layout, Dict, List]] = None,
            seed_transpiler: Optional[int] = None,
            optimization_level: Optional[int] = None,
            transpiler_options: Optional[dict] = None,
            scheduling_method: Optional[str] = None,
            shots: Optional[int] = None,
            memory: Optional[bool] = None,
            memory_slots: Optional[int] = None,
            memory_slot_size: Optional[int] = None,
            rep_time: Optional[int] = None,
            rep_delay: Optional[float] = None,
            parameter_binds: Optional[List[Dict[Parameter, float]]] = None,
            schedule_circuit=False,
            inst_map: InstructionScheduleMap = None,
            meas_map: List[List[int]] = None,
            init_qubits: Optional[bool] = None,
            **run_config: Dict
    ) -> 'RuntimeJob':
        """Execute the input circuit(s) on a backend using the runtime service.

        Note:
            This method uses the IBM Quantum runtime service which is not
            available to all accounts.

        Args:
            circuits: Circuit(s) to execute.

            backend: Backend to execute circuits on.
                Transpiler options are automatically grabbed from backend configuration
                and properties unless otherwise specified.

            initial_layout: Initial position of virtual qubits on physical qubits.

            seed_transpiler: Sets random seed for the stochastic parts of the transpiler.

            optimization_level: How much optimization to perform on the circuits.
                Higher levels generate more optimized circuits, at the expense of longer
                transpilation time.
                If None, level 1 will be chosen as default.

            transpiler_options: Additional transpiler options.

            scheduling_method: Scheduling method.

            shots: Number of repetitions of each circuit, for sampling. Default: 1024.

            memory: If True, per-shot measurement bitstrings are returned as well
                (provided the backend supports it). Default: False

            memory_slots: Number of classical memory slots used in this job.

            memory_slot_size: Size of each memory slot if the output is Level 0.

            rep_time: Time per program execution in seconds. Must be from the list provided
                by the backend configuration (``backend.configuration().rep_times``).
                Defaults to the first entry.

            rep_delay: Delay between programs in seconds. Only supported on certain
                backends (``backend.configuration().dynamic_reprate_enabled`` ). If supported,
                ``rep_delay`` will be used instead of ``rep_time`` and must be from the
                range supplied by the backend (``backend.configuration().rep_delay_range``).
                Default is given by ``backend.configuration().default_rep_delay``.

            parameter_binds: List of Parameter bindings over which the set of
                experiments will be executed. Each list element (bind) should be of the form
                ``{Parameter1: value1, Parameter2: value2, ...}``. All binds will be
                executed across all experiments, e.g. if parameter_binds is a
                length-n list, and there are m experiments, a total of :math:`m x n`
                experiments will be run (one for each experiment/bind pair).

            schedule_circuit: If ``True``, ``circuits`` will be converted to
                :class:`qiskit.pulse.Schedule` objects prior to execution.

            inst_map: Mapping of circuit operations to pulse schedules. If None, defaults to the
                ``instruction_schedule_map`` of ``backend``.

            meas_map: List of sets of qubits that must be measured together. If None,
                defaults to the ``meas_map`` of ``backend``.

            init_qubits: Whether to reset the qubits to the ground state for each shot.
                Default: ``True``.

            **run_config: Extra arguments used to configure the circuit execution.

        Returns:
            Runtime job.
        """
        inputs = {
            'circuits': circuits,
            'initial_layout': initial_layout,
            'seed_transpiler': seed_transpiler,
            'optimization_level': optimization_level,
            'scheduling_method': scheduling_method,
            'shots': shots,
            'memory': memory,
            'memory_slots': memory_slots,
            'memory_slot_size': memory_slot_size,
            'rep_time': rep_time,
            'rep_delay': rep_delay,
            'parameter_binds': parameter_binds,
            'schedule_circuit': schedule_circuit,
            'inst_map': inst_map,
            'meas_map': meas_map,
            'init_qubits': init_qubits,
            'transpiler_options': transpiler_options
        }
        inputs.update(run_config)
        options = {'backend_name': backend.name()}
        return self.runtime.run('circuit-runner-jessie3', options=options, inputs=inputs)

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

    @property
    def runtime(self) -> IBMRuntimeService:
        """Return the runtime service.

        Returns:
            The runtime service instance.
        """
        return self._runtime

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
