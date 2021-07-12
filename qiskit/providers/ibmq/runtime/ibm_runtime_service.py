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

"""Qiskit runtime service."""

import logging
from typing import Dict, Callable, Optional, Union, List, Any, Type
import json
import copy

from qiskit.providers.exceptions import QiskitBackendNotFoundError
from qiskit.providers.ibmq import accountprovider  # pylint: disable=unused-import

from .runtime_job import RuntimeJob
from .runtime_program import RuntimeProgram, ProgramParameter, ProgramResult, ParameterNamespace
from .utils import RuntimeEncoder, RuntimeDecoder
from .exceptions import (QiskitRuntimeError, RuntimeDuplicateProgramError, RuntimeProgramNotFound,
                         RuntimeJobNotFound)
from .program.result_decoder import ResultDecoder
from ..api.clients.runtime import RuntimeClient

from ..api.exceptions import RequestsApiError
from ..exceptions import IBMQNotAuthorizedError, IBMQInputValueError, IBMQProviderError
from ..ibmqbackend import IBMQRetiredBackend
from ..credentials import Credentials

logger = logging.getLogger(__name__)


class IBMRuntimeService:
    """Class for interacting with the Qiskit Runtime service.

    Qiskit Runtime is a new architecture offered by IBM Quantum that
    streamlines computations requiring many iterations. These experiments will
    execute significantly faster within its improved hybrid quantum/classical
    process.

    The Qiskit Runtime Service allows authorized users to upload their Qiskit
    quantum programs. A Qiskit quantum program, also called a runtime program,
    is a piece of Python code and its metadata that takes certain inputs, performs
    quantum and maybe classical processing, and returns the results. The same or other
    authorized users can invoke these quantum programs by simply passing in parameters.

    A sample workflow of using the runtime service::

        from qiskit import IBMQ, QuantumCircuit
        from qiskit.providers.ibmq import RunnerResult

        provider = IBMQ.load_account()
        backend = provider.backend.ibmq_qasm_simulator

        # List all available programs.
        provider.runtime.pprint_programs()

        # Create a circuit.
        qc = QuantumCircuit(2, 2)
        qc.h(0)
        qc.cx(0, 1)
        qc.measure_all()

        # Set the "circuit-runner" program parameters
        params = provider.runtime.program(program_id="circuit-runner").parameters()
        params.circuits = qc
        params.measurement_error_mitigation = True

        # Configure backend options
        options = {'backend_name': backend.name()}

        # Execute the circuit using the "circuit-runner" program.
        job = provider.runtime.run(program_id="circuit-runner",
                                   options=options,
                                   inputs=params)

        # Get runtime job result.
        result = job.result(decoder=RunnerResult)

    If the program has any interim results, you can use the ``callback``
    parameter of the :meth:`run` method to stream the interim results.
    Alternatively, you can use the :meth:`RuntimeJob.stream_results` method to stream
    the results at a later time, but before the job finishes.

    The :meth:`run` method returns a
    :class:`~qiskit.providers.ibmq.runtime.RuntimeJob` object. You can use its
    methods to perform tasks like checking job status, getting job result, and
    canceling job.
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
        self._programs = {}  # type: Dict

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

        Currently only program metadata is returned.

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

        Currently only program metadata is returned.

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
        backend_req = json.loads(response.get('backendRequirements', '{}'))
        params = json.loads(response.get('parameters', '{}')).get("doc", [])
        ret_vals = json.loads(response.get('returnValues', '{}'))
        interim_results = json.loads(response.get('interimResults', '{}'))

        return RuntimeProgram(program_name=response['name'],
                              program_id=response['id'],
                              description=response.get('description', ""),
                              parameters=params,
                              return_values=ret_vals,
                              interim_results=interim_results,
                              max_execution_time=response.get('cost', 0),
                              creation_date=response.get('creationDate', ""),
                              version=response.get('version', "0"),
                              backend_requirements=backend_req,
                              is_public=response.get('isPublic', False))

    def run(
            self,
            program_id: str,
            options: Dict,
            inputs: Union[Dict, ParameterNamespace],
            callback: Optional[Callable] = None,
            result_decoder: Optional[Type[ResultDecoder]] = None
    ) -> RuntimeJob:
        """Execute the runtime program.

        Args:
            program_id: Program ID.
            options: Runtime options that control the execution environment.
                Currently the only available option is ``backend_name``, which is required.
            inputs: Program input parameters. These input values are passed
                to the runtime program.
            callback: Callback function to be invoked for any interim results.
                The callback function will receive 2 positional parameters:

                    1. Job ID
                    2. Job interim result.

            result_decoder: A :class:`ResultDecoder` subclass used to decode job results.
                ``ResultDecoder`` is used if not specified.

        Returns:
            A ``RuntimeJob`` instance representing the execution.

        Raises:
            IBMQInputValueError: If input is invalid.
        """
        if 'backend_name' not in options:
            raise IBMQInputValueError('"backend_name" is required field in "options"')
        # If using params object, extract as dictionary
        if isinstance(inputs, ParameterNamespace):
            inputs.validate()
            inputs = vars(inputs)

        backend_name = options['backend_name']
        params_str = json.dumps(inputs, cls=RuntimeEncoder)
        result_decoder = result_decoder or ResultDecoder
        response = self._api_client.program_run(program_id=program_id,
                                                credentials=self._provider.credentials,
                                                backend_name=backend_name,
                                                params=params_str)

        backend = self._provider.get_backend(backend_name)
        job = RuntimeJob(backend=backend,
                         api_client=self._api_client,
                         credentials=self._provider.credentials,
                         job_id=response['id'], program_id=program_id, params=inputs,
                         user_callback=callback,
                         result_decoder=result_decoder)
        return job

    def upload_program(
            self,
            data: Union[bytes, str],
            metadata: Optional[Union[Dict, str]] = None,
            name: Optional[str] = None,
            max_execution_time: Optional[int] = None,
            description: Optional[str] = None,
            version: Optional[float] = None,
            backend_requirements: Optional[str] = None,
            parameters: Optional[List[ProgramParameter]] = None,
            return_values: Optional[List[ProgramResult]] = None,
            interim_results: Optional[List[ProgramResult]] = None
    ) -> str:
        """Upload a runtime program.

        In addition to program data, the following program metadata is also
        required:

            - name
            - max_execution_time
            - description

        Program metadata can be specified using the `metadata` parameter or
        individual parameter (for example, `name` and `description`). If the
        same metadata field is specified in both places, the individual parameter
        takes precedence. For example, if you specify::

            upload_program(metadata={"name": "name1"}, name="name2")

        ``name2`` will be used as the program name.

        Args:
            data: Name of the program file or program data to upload.
            metadata: Name of the program metadata file or metadata dictionary.
                A metadata file needs to be in the JSON format.
                See :file:`program/program_metadata_sample.yaml` for an example.
            name: Name of the program. Required if not specified via `metadata`.
            max_execution_time: Maximum execution time in seconds. Required if
                not specified via `metadata`.
            description: Program description. Required if not specified via `metadata`.
            version: Program version. The default is 1.0 if not specified.
            backend_requirements: Backend requirements.
            parameters: A list of program input parameters.
            return_values: A list of program return values.
            interim_results: A list of program interim results.

        Returns:
            Program ID.

        Raises:
            IBMQInputValueError: If required metadata is missing.
            RuntimeDuplicateProgramError: If a program with the same name already exists.
            IBMQNotAuthorizedError: If you are not authorized to upload programs.
            QiskitRuntimeError: If the upload failed.
        """
        program_metadata = self._merge_metadata(
            initial={},
            metadata=metadata,
            name=name, max_execution_time=max_execution_time, description=description,
            version=version, backend_requirements=backend_requirements,
            parameters=parameters,
            return_values=return_values, interim_results=interim_results)

        for req in ['name', 'description', 'max_execution_time']:
            if req not in program_metadata or not program_metadata[req]:
                raise IBMQInputValueError(f"{req} is a required metadata field.")

        try:
            response = self._api_client.program_create(program_data=data, **program_metadata)
        except RequestsApiError as ex:
            if ex.status_code == 409:
                raise RuntimeDuplicateProgramError(
                    "Program with the same name already exists.") from None
            if ex.status_code == 403:
                raise IBMQNotAuthorizedError(
                    "You are not authorized to upload programs.") from None
            raise QiskitRuntimeError(f"Failed to create program: {ex}") from None
        return response['id']

    def _merge_metadata(
            self,
            initial: Dict,
            metadata: Optional[Union[Dict, str]] = None,
            **kwargs: Any
    ) -> Dict:
        """Merge multiple copies of metadata.

        Args:
            initial: The initial metadata. This may be mutated.
            metadata: Name of the program metadata file or metadata dictionary.
            **kwargs: Additional metadata fields to overwrite.

        Returns:
            Merged metadata.
        """
        upd_metadata: dict = {}
        if metadata is not None:
            if isinstance(metadata, str):
                with open(metadata, 'r') as file:
                    upd_metadata = json.load(file)
            else:
                upd_metadata = copy.deepcopy(metadata)

        self._tuple_to_dict(initial)
        initial.update(upd_metadata)

        self._tuple_to_dict(kwargs)
        for key, val in kwargs.items():
            if val is not None:
                initial[key] = val

        # TODO validate metadata format
        metadata_keys = ['name', 'max_execution_time', 'description', 'version',
                         'backend_requirements', 'parameters', 'return_values',
                         'interim_results']
        return {key: val for key, val in initial.items() if key in metadata_keys}

    def _tuple_to_dict(self, metadata: Dict) -> None:
        """Convert fields in metadata from named tuples to dictionaries.

        Args:
            metadata: Metadata to be converted.
        """
        for key in ['parameters', 'return_values', 'interim_results']:
            doc_list = metadata.pop(key, None)
            if not doc_list or isinstance(doc_list[0], dict):
                continue
            metadata[key] = [dict(elem._asdict()) for elem in doc_list]

    def delete_program(self, program_id: str) -> None:
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

    def set_program_visibility(self, program_id: str, public: bool) -> None:
        """Sets a program's visibility.

        Args:
            program_id: Program ID.
            public: If ``True``, make the program visible to all.
                If ``False``, make the program visible to just your account.

        Raises:
            RuntimeJobNotFound: if program not found (404)
            QiskitRuntimeError: if update failed (401, 403)
        """
        try:
            self._api_client.set_program_visibility(program_id, public)
        except RequestsApiError as ex:
            if ex.status_code == 404:
                raise RuntimeJobNotFound(f"Program not found: {ex.message}") from None
            raise QiskitRuntimeError(f"Failed to set program visibility: {ex}") from None

    def job(self, job_id: str) -> RuntimeJob:
        """Retrieve a runtime job.

        Args:
            job_id: Job ID.

        Returns:
            Runtime job retrieved.

        Raises:
            RuntimeJobNotFound: If the job doesn't exist.
            QiskitRuntimeError: If the request failed.
        """
        try:
            response = self._api_client.job_get(job_id)
        except RequestsApiError as ex:
            if ex.status_code == 404:
                raise RuntimeJobNotFound(f"Job not found: {ex.message}") from None
            raise QiskitRuntimeError(f"Failed to delete job: {ex}") from None
        return self._decode_job(response)

    def jobs(self, limit: int = 10, skip: int = 0, pending: bool = None) -> List[RuntimeJob]:
        """Retrieve all runtime jobs, subject to optional filtering.

        Args:
            limit: Number of jobs to retrieve.
            skip: Starting index for the job retrieval.
            pending: Filter by job pending state. If ``True``, 'QUEUED' and 'RUNNING'
                jobs are included. If ``False``, 'DONE', 'CANCELLED' and 'ERROR' jobs
                are included.

        Returns:
            A list of runtime jobs.
        """
        job_responses = []  # type: List[Dict[str, Any]]
        current_page_limit = limit or 20

        while True:
            job_page = self._api_client.jobs_get(
                limit=current_page_limit,
                skip=skip,
                pending=pending)["jobs"]
            if not job_page:
                # Stop if there are no more jobs returned by the server.
                break

            job_responses += job_page
            if limit:
                if len(job_responses) >= limit:
                    # Stop if we have reached the limit.
                    break
                current_page_limit = limit - len(job_responses)
            else:
                current_page_limit = 20

            skip += len(job_page)

        return [self._decode_job(job) for job in job_responses]

    def delete_job(self, job_id: str) -> None:
        """Delete a runtime job.

        Note that this operation cannot be reversed.

        Args:
            job_id: ID of the job to delete.

        Raises:
            RuntimeJobNotFound: If the job doesn't exist.
            QiskitRuntimeError: If the request failed.
        """
        try:
            self._api_client.job_delete(job_id)
        except RequestsApiError as ex:
            if ex.status_code == 404:
                raise RuntimeJobNotFound(f"Job not found: {ex.message}") from None
            raise QiskitRuntimeError(f"Failed to delete job: {ex}") from None

    def _decode_job(self, raw_data: Dict) -> RuntimeJob:
        """Decode job data received from the server.

        Args:
            raw_data: Raw job data received from the server.

        Returns:
            Decoded job data.
        """
        hub = raw_data['hub']
        group = raw_data['group']
        project = raw_data['project']
        if self._provider.credentials.unique_id().to_tuple() != (hub, group, project):
            # Try to find the right backend
            try:
                original_provider = self._provider._factory.get_provider(hub, group, project)
                backend = original_provider.get_backend(raw_data['backend'])
            except (IBMQProviderError, QiskitBackendNotFoundError):
                backend = IBMQRetiredBackend.from_name(
                    backend_name=raw_data['backend'],
                    provider=None,
                    credentials=Credentials(token="", url="",
                                            hub=hub, group=group, project=project),
                    api=None
                )
        else:
            backend = self._provider.get_backend(raw_data['backend'])

        params = raw_data.get('params', {})
        if isinstance(params, list):
            if len(params) > 0:
                params = params[0]
            else:
                params = {}
        if not isinstance(params, str):
            params = json.dumps(params)

        decoded = json.loads(params, cls=RuntimeDecoder)
        return RuntimeJob(backend=backend,
                          api_client=self._api_client,
                          credentials=self._provider.credentials,
                          job_id=raw_data['id'],
                          program_id=raw_data.get('program', {}).get('id', ""),
                          params=decoded,
                          creation_date=raw_data.get('created', None))

    def logout(self) -> None:
        """Clears authorization cache on the server.

        For better performance, the runtime server caches each user's
        authorization information. This method is used to force the server
        to clear its cache.

        Note:
            Invoke this method ONLY when your access level to the runtime
            service has changed - for example, the first time your account is
            given the authority to upload a program.
        """
        self._api_client.logout()
