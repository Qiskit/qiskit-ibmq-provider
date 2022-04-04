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
import warnings

from qiskit.providers.exceptions import QiskitBackendNotFoundError
from qiskit.providers.ibmq import accountprovider  # pylint: disable=unused-import

from .runtime_job import RuntimeJob
from .runtime_program import RuntimeProgram, ParameterNamespace
from .utils import RuntimeDecoder, to_base64_string
from .exceptions import (QiskitRuntimeError, RuntimeDuplicateProgramError, RuntimeProgramNotFound,
                         RuntimeJobNotFound)
from .program.result_decoder import ResultDecoder
from .runtime_options import RuntimeOptions
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

    def pprint_programs(self, refresh: bool = False, detailed: bool = False,
                        limit: int = 20, skip: int = 0) -> None:
        """Pretty print information about available runtime programs.

        Args:
            refresh: If ``True``, re-query the server for the programs. Otherwise
                return the cached value.
            detailed: If ``True`` print all details about available runtime programs.
            limit: The number of programs returned at a time. Default and maximum
                value of 20.
            skip: The number of programs to skip.
        """
        programs = self.programs(refresh, limit, skip)
        for prog in programs:
            print("="*50)
            if detailed:
                print(str(prog))
            else:
                print(f"{prog.program_id}:",)
                print(f"  Name: {prog.name}")
                print(f"  Description: {prog.description}")

    def programs(self, refresh: bool = False,
                 limit: int = 20, skip: int = 0) -> List[RuntimeProgram]:
        """Return available runtime programs.

        Currently only program metadata is returned.

        Args:
            refresh: If ``True``, re-query the server for the programs. Otherwise
                return the cached value.
            limit: The number of programs returned at a time. ``None`` means no limit.
            skip: The number of programs to skip.

        Returns:
            A list of runtime programs.
        """
        if skip is None:
            skip = 0
        if not self._programs or refresh:
            self._programs = {}
            current_page_limit = 20
            offset = 0
            while True:
                response = self._api_client.list_programs(limit=current_page_limit, skip=offset)
                program_page = response.get("programs", [])
                # count is the total number of programs that would be returned if
                # there was no limit or skip
                count = response.get("count", 0)
                for prog_dict in program_page:
                    program = self._to_program(prog_dict)
                    self._programs[program.program_id] = program
                if len(self._programs) == count:
                    # Stop if there are no more programs returned by the server.
                    break
                offset += len(program_page)
        if limit is None:
            limit = len(self._programs)
        return list(self._programs.values())[skip:limit+skip]

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
        backend_requirements = {}
        parameters = {}
        return_values = {}
        interim_results = {}
        if "spec" in response:
            backend_requirements = response["spec"].get('backend_requirements', {})
            parameters = response["spec"].get('parameters', {})
            return_values = response["spec"].get('return_values', {})
            interim_results = response["spec"].get('interim_results', {})

        return RuntimeProgram(program_name=response['name'],
                              program_id=response['id'],
                              description=response.get('description', ""),
                              parameters=parameters,
                              return_values=return_values,
                              interim_results=interim_results,
                              max_execution_time=response.get('cost', 0),
                              creation_date=response.get('creation_date', ""),
                              update_date=response.get('update_date', ""),
                              backend_requirements=backend_requirements,
                              is_public=response.get('is_public', False),
                              data=response.get('data', ""),
                              api_client=self._api_client)

    def run(
            self,
            program_id: str,
            options: Union[RuntimeOptions, Dict],
            inputs: Union[Dict, ParameterNamespace],
            callback: Optional[Callable] = None,
            result_decoder: Optional[Type[ResultDecoder]] = None,
            image: Optional[str] = ""
    ) -> RuntimeJob:
        """Execute the runtime program.

        Args:
            program_id: Program ID.
            options: Runtime options that control the execution environment. See
                :class:`RuntimeOptions` for all available options.
                Currently the only required option is ``backend_name``.
            inputs: Program input parameters. These input values are passed
                to the runtime program.
            callback: Callback function to be invoked for any interim results.
                The callback function will receive 2 positional parameters:

                    1. Job ID
                    2. Job interim result.

            result_decoder: A :class:`ResultDecoder` subclass used to decode job results.
                ``ResultDecoder`` is used if not specified.
            image: (DEPRECATED) The runtime image used to execute the program, specified in the
                form of image_name:tag. Not all accounts are authorized to select a different
                image.

        Returns:
            A ``RuntimeJob`` instance representing the execution.

        Raises:
            IBMQInputValueError: If input is invalid.
        """
        if isinstance(options, dict):
            options = RuntimeOptions(**options)

        if image:
            warnings.warn("Passing the 'image' keyword to IBMRuntimeService.run is "
                          "deprecated and will be removed in a future release. "
                          "Please pass it in as part of 'options'.",
                          DeprecationWarning, stacklevel=2)
            options.image = image

        options.validate()

        # If using params object, extract as dictionary
        if isinstance(inputs, ParameterNamespace):
            inputs.validate()
            inputs = vars(inputs)

        backend_name = options.backend_name
        result_decoder = result_decoder or ResultDecoder
        response = self._api_client.program_run(program_id=program_id,
                                                credentials=self._provider.credentials,
                                                backend_name=backend_name,
                                                params=inputs,
                                                image=options.image,
                                                log_level=options.log_level)

        backend = self._provider.get_backend(backend_name)
        job = RuntimeJob(backend=backend,
                         api_client=self._api_client,
                         credentials=self._provider.credentials,
                         job_id=response['id'], program_id=program_id, params=inputs,
                         user_callback=callback,
                         result_decoder=result_decoder,
                         image=options.image)
        return job

    def upload_program(
            self,
            data: str,
            metadata: Optional[Union[Dict, str]] = None
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
            data: Program data or path of the file containing program data to upload.
            metadata: Name of the program metadata file or metadata dictionary.
                A metadata file needs to be in the JSON format. The ``parameters``,
                ``return_values``, and ``interim_results`` should be defined as JSON Schema.
                See :file:`program/program_metadata_sample.json` for an example. The
                fields in metadata are explained below.

                * name: Name of the program. Required.
                * max_execution_time: Maximum execution time in seconds. Required.
                * description: Program description. Required.
                * is_public: Whether the runtime program should be visible to the public.
                                    The default is ``False``.
                * spec: Specifications for backend characteristics and input parameters
                    required to run the program, interim results and final result.

                    * backend_requirements: Backend requirements.
                    * parameters: Program input parameters in JSON schema format.
                    * return_values: Program return values in JSON schema format.
                    * interim_results: Program interim results in JSON schema format.

        Returns:
            Program ID.

        Raises:
            IBMQInputValueError: If required metadata is missing.
            RuntimeDuplicateProgramError: If a program with the same name already exists.
            IBMQNotAuthorizedError: If you are not authorized to upload programs.
            QiskitRuntimeError: If the upload failed.
        """
        program_metadata = self._read_metadata(metadata=metadata)

        for req in ['name', 'description', 'max_execution_time']:
            if req not in program_metadata or not program_metadata[req]:
                raise IBMQInputValueError(f"{req} is a required metadata field.")

        if "def main(" not in data:
            # This is the program file
            with open(data, "r") as file:
                data = file.read()

        try:
            program_data = to_base64_string(data)
            response = self._api_client.program_create(program_data=program_data,
                                                       **program_metadata)
        except RequestsApiError as ex:
            if ex.status_code == 409:
                raise RuntimeDuplicateProgramError(
                    "Program with the same name already exists.") from None
            if ex.status_code == 403:
                raise IBMQNotAuthorizedError(
                    "You are not authorized to upload programs.") from None
            raise QiskitRuntimeError(f"Failed to create program: {ex}") from None
        return response['id']

    def _read_metadata(
            self,
            metadata: Optional[Union[Dict, str]] = None
    ) -> Dict:
        """Read metadata.

        Args:
            metadata: Name of the program metadata file or metadata dictionary.

        Returns:
            Return metadata.
        """
        upd_metadata: dict = {}
        if metadata is not None:
            if isinstance(metadata, str):
                with open(metadata, 'r') as file:
                    upd_metadata = json.load(file)
            else:
                upd_metadata = metadata
        # TODO validate metadata format
        metadata_keys = ['name', 'max_execution_time', 'description',
                         'spec', 'is_public']
        return {key: val for key, val in upd_metadata.items() if key in metadata_keys}

    def update_program(
            self,
            program_id: str,
            data: str = None,
            metadata: Optional[Union[Dict, str]] = None,
            name: str = None,
            description: str = None,
            max_execution_time: int = None,
            spec: Optional[Dict] = None
    ) -> None:
        """Update a runtime program.

        Program metadata can be specified using the `metadata` parameter or
        individual parameters, such as `name` and `description`. If the
        same metadata field is specified in both places, the individual parameter
        takes precedence.

        Args:
            program_id: Program ID.
            data: Program data or path of the file containing program data to upload.
            metadata: Name of the program metadata file or metadata dictionary.
            name: New program name.
            description: New program description.
            max_execution_time: New maximum execution time.
            spec: New specifications for backend characteristics, input parameters,
                interim results and final result.

        Raises:
            RuntimeProgramNotFound: If the program doesn't exist.
            QiskitRuntimeError: If the request failed.
        """
        if not any([data, metadata, name, description, max_execution_time, spec]):
            warnings.warn("None of the 'data', 'metadata', 'name', 'description', "
                          "'max_execution_time', or 'spec' parameters is specified. "
                          "No update is made.")
            return

        if data:
            if "def main(" not in data:
                # This is the program file
                with open(data, "r") as file:
                    data = file.read()
            data = to_base64_string(data)

        if metadata:
            metadata = self._read_metadata(metadata=metadata)
        combined_metadata = self._merge_metadata(
            metadata=metadata, name=name, description=description,
            max_execution_time=max_execution_time, spec=spec)

        try:
            self._api_client.program_update(
                program_id, program_data=data, **combined_metadata)
        except RequestsApiError as ex:
            if ex.status_code == 404:
                raise RuntimeProgramNotFound(f"Program not found: {ex.message}") from None
            raise QiskitRuntimeError(f"Failed to update program: {ex}") from None

        if program_id in self._programs:
            program = self._programs[program_id]
            program._refresh()

    def _merge_metadata(
            self,
            metadata: Optional[Dict] = None,
            **kwargs: Any
    ) -> Dict:
        """Merge multiple copies of metadata.
        Args:
            metadata: Program metadata.
            **kwargs: Additional metadata fields to overwrite.
        Returns:
            Merged metadata.
        """
        merged = {}
        metadata = metadata or {}
        metadata_keys = ['name', 'max_execution_time', 'description', 'spec']
        for key in metadata_keys:
            if kwargs.get(key, None) is not None:
                merged[key] = kwargs[key]
            elif key in metadata.keys():
                merged[key] = metadata[key]
        return merged

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

        if program_id in self._programs:
            program = self._programs[program_id]
            program._is_public = public

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

    def jobs(
            self,
            limit: Optional[int] = 10,
            skip: int = 0,
            pending: bool = None,
            program_id: str = None
    ) -> List[RuntimeJob]:
        """Retrieve all runtime jobs, subject to optional filtering.

        Args:
            limit: Number of jobs to retrieve. ``None`` means no limit.
            skip: Starting index for the job retrieval.
            pending: Filter by job pending state. If ``True``, 'QUEUED' and 'RUNNING'
                jobs are included. If ``False``, 'DONE', 'CANCELLED' and 'ERROR' jobs
                are included.
            program_id: Filter by Program ID.

        Returns:
            A list of runtime jobs.
        """
        job_responses = []  # type: List[Dict[str, Any]]
        current_page_limit = limit or 20
        offset = skip

        while True:
            jobs_response = self._api_client.jobs_get(
                limit=current_page_limit,
                skip=offset,
                pending=pending,
                program_id=program_id)
            job_page = jobs_response["jobs"]
            # count is the total number of jobs that would be returned if
            # there was no limit or skip
            count = jobs_response["count"]

            job_responses += job_page

            if len(job_responses) == count - skip:
                # Stop if there are no more jobs returned by the server.
                break

            if limit:
                if len(job_responses) >= limit:
                    # Stop if we have reached the limit.
                    break
                current_page_limit = limit - len(job_responses)
            else:
                current_page_limit = 20

            offset += len(job_page)

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
