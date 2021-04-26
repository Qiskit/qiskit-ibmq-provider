# This code is part of Qiskit.
#
# (C) Copyright IBM 2021.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""IBM Quantum runtime service."""

import logging
from typing import Dict, Callable, Optional, Union, List
import json

from qiskit.providers.ibmq import accountprovider  # pylint: disable=unused-import

from .runtime_job import RuntimeJob
from .runtime_program import RuntimeProgram
from .utils import RuntimeEncoder, RuntimeDecoder
from .exceptions import QiskitRuntimeError, RuntimeDuplicateProgramError, RuntimeProgramNotFound
from ..api.clients.runtime import RuntimeClient
from ..api.clients.runtime_ws import RuntimeWebsocketClient
from ..api.exceptions import RequestsApiError
from ..exceptions import IBMQNotAuthorizedError, IBMQInputValueError

logger = logging.getLogger(__name__)


class IBMRuntimeService:
    """Class for interacting with the IBM Quantum runtime service.

    The IBM Quantum Runtime Service allows authorized users to upload their quantum programs
    that can be invoked by others. A quantum program is a piece of code that takes
    certain inputs, performs quantum and classical processing, and returns the
    results.

    A sample workflow of using the runtime service::

        from qiskit import IBMQ, QuantumCircuit

        provider = IBMQ.load_account()
        backend = provider.backend.ibmq_qasm_simulator

        # List all available programs.
        provider.runtime.pprint_programs()

        # Create a circuit.
        qc = QuantumCircuit(2, 2)
        qc.h(0)
        qc.cx(0, 1)
        qc.measure_all()

        # Execute the circuit using the "circuit-runner" program.
        runtime_inputs = {'circuits': circuit, 'measurement_error_mitigation': True}
        options = {'backend_name': backend.name()}
        job = provider.runtime.run(program_id="circuit-runner",
                                   options=options,
                                   inputs=runtime_inputs)

        # Get runtime job result.
        result = job.result()

    If the program has any interim results, you can use the ``callback``
    parameter of the :meth:`run` method to stream the interim results.
    Alternatively, you can use the :meth:`stream_results` method to stream
    the results at a later time, but before the job finishes.

    The :meth:`run` method returns a
    :class:`qiskit.providers.ibmq.runtime.RuntimeJob` object. You can use its
    methods to perform tasks like checking the job status, getting job result, and
    canceling the job.
    """

    def __init__(self, provider: 'accountprovider.AccountProvider') -> None:
        """IBMRuntimeService constructor.

        Args:
            provider: IBM Quantum account provider.
        """
        self._provider = provider
        self._api_client = RuntimeClient(provider.credentials)
        self._access_token = provider.credentials.access_token
        self._ws_url = provider.credentials.runtime_url.replace('https', 'wss')
        self._programs = {}

    def pprint_programs(self, refresh: bool = False) -> None:
        """Pretty print information about available runtime programs.

        Args:
            refresh: If ``True``, re-query the server for the programs. Otherwise
                return the cached value.
        """
        programs = self.programs(refresh)
        for prog in programs:
            print("="*50)
            print(str(prog))

    def programs(self, refresh: bool = False) -> List[RuntimeProgram]:
        """Return available runtime programs.

        Args:
            refresh: If ``True``, re-query the server for the programs. Otherwise
                return the cached value.

        Returns:
            A list of runtime programs.
        """
        if not self._programs or refresh:
            self._programs = {}
            response = self._api_client.list_programs()
            for prog_dict in response:
                program = self._to_program(prog_dict)
                self._programs[program.program_id] = program
        return list(self._programs.values())

    def program(self, program_id: str, refresh: bool = False) -> RuntimeProgram:
        """Retrieve a runtime program.

        Args:
            program_id: Program ID.
            refresh: If ``True``, re-query the server for the program. Otherwise
                return the cached value.

        Returns:
            Runtime program.

        Raises:
            RuntimeProgramNotFound: If the program does not exist.
            QiskitRuntimeError: If the request failed.
        """
        if program_id not in self._programs or refresh:
            try:
                response = self._api_client.program_get(program_id)
            except RequestsApiError as ex:
                if ex.status_code == 404:
                    raise RuntimeProgramNotFound(f"Program not found: {ex.message}") from None
                raise QiskitRuntimeError(f"Failed to get program: {ex}") from None

            self._programs[program_id] = self._to_program(response)

        return self._programs[program_id]

    def _to_program(self, response: Dict) -> RuntimeProgram:
        """Convert server response to ``RuntimeProgram`` instances.

        Args:
            response: Server response.

        Returns:
            A ``RuntimeProgram`` instance.
        """
        return RuntimeProgram(program_name=response['name'],
                              program_id=response['id'],
                              description=response.get('description', ""),
                              parameters=response.get('parameters', None),
                              return_values=response.get('return_values', None),
                              max_execution_time=response.get('cost', 0))

    def run(
            self,
            program_id: str,
            options: Dict,
            inputs: Dict,
            callback: Optional[Callable] = None
    ) -> RuntimeJob:
        """Execute the runtime program.

        Args:
            program_id: Program ID.
            options: Runtime options. Currently the only available option is
                ``backend_name``, which is required.
            inputs: Program input parameters.
            callback: Callback function to be invoked for any interim results.

        Returns:
            A ``RuntimeJob`` instance representing the execution.

        Raises:
            IBMQInputValueError: If input is invalid.
        """
        if 'backend_name' not in options:
            raise IBMQInputValueError('"backend_name" is required field in "options"')

        backend_name = options['backend_name']
        params_str = json.dumps(inputs, cls=RuntimeEncoder)
        response = self._api_client.program_run(program_id=program_id,
                                                credentials=self._provider.credentials,
                                                backend_name=backend_name,
                                                params=params_str)

        backend = self._provider.get_backend(backend_name)
        job = RuntimeJob(backend=backend,
                         api_client=self._api_client,
                         ws_client=RuntimeWebsocketClient(self._ws_url, self._access_token),
                         job_id=response['id'], program_id=program_id, params=inputs,
                         user_callback=callback)
        return job

    def upload_program(
            self,
            name: str,
            data: Union[bytes, str],
            max_execution_time: int
    ) -> str:
        """Upload a runtime program.

        Args:
            name: Name of the program.
            data: Name of the program file or program data to upload.
            max_execution_time: Maximum execution time in seconds.

        Returns:
            Program ID.

        Raises:
            RuntimeDuplicateProgramError: If a program with the same name already exists.
            IBMQNotAuthorizedError: If you are not authorized to upload programs.
            QiskitRuntimeError: If the upload failed.
        """
        try:
            response = self._api_client.program_create(name, data, max_execution_time)
        except RequestsApiError as ex:
            if ex.status_code == 409:
                raise RuntimeDuplicateProgramError(
                    "Program with the same name already exists.") from None
            if ex.status_code == 403:
                raise IBMQNotAuthorizedError(
                    "You are not authorized to upload programs.") from None
            raise QiskitRuntimeError(f"Failed to create program: {ex}") from None
        return response['id']

    def delete_program(self, program_id: str):
        """Delete a runtime program.

        Args:
            program_id: Program ID.

        Raises:
            RuntimeProgramNotFound: If the program doesn't exist.
            QiskitRuntimeError: If the request failed.
        """
        try:
            self._api_client.program_delete(program_id=program_id)
        except RequestsApiError as ex:
            if ex.status_code == 404:
                raise RuntimeProgramNotFound(f"Program not found: {ex.message}") from None
            raise QiskitRuntimeError(f"Failed to delete program: {ex}") from None

        if program_id in self._programs:
            del self._programs[program_id]

    def job(self, job_id: str) -> RuntimeJob:
        """Retrieve a runtime job.

        Args:
            job_id: Job ID.

        Returns:
            Runtime job retrieved.
        """
        response = self._api_client.job_get(job_id)
        backend = self._provider.get_backend(response['backend'])
        params_str = json.dumps(response.get('params', {}))
        params = json.loads(params_str, cls=RuntimeDecoder)
        return RuntimeJob(backend=backend,
                          api_client=self._api_client,
                          ws_client=RuntimeWebsocketClient(self._ws_url, self._access_token),
                          job_id=response['id'],
                          program_id=response.get('program', {}).get('id', ""),
                          params=params)
