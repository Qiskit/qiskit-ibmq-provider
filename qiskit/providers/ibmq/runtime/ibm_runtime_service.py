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
from qiskit import QiskitError

from .runtime_job import RuntimeJob
from .runtime_program import RuntimeProgram
from .utils import RuntimeEncoder
from ..api.clients.runtime import RuntimeClient

logger = logging.getLogger(__name__)


class IBMRuntimeService:
    """IBM Quantum runtime service."""

    def __init__(self, provider: 'accountprovider.AccountProvider', access_token: str) -> None:
        """IBMRuntimeService constructor.

        Args:
            provider: IBM Quantum account provider.
            access_token: IBM Quantum access token.
        """
        self._provider = provider
        self._api_client = RuntimeClient(access_token, provider.credentials)
        self._programs = {}

    def print_programs(self, refresh: bool = False) -> None:
        """Print information about available runtime programs.

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
        """
        if program_id not in self._programs or refresh:
            response = self._api_client.program_get(program_id)
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
            params: Dict,
            callback: Optional[Callable] = None
    ) -> RuntimeJob:
        """Execute the runtime program.

        Args:
            program_id: Program ID.
            options: Runtime options. Currently the only available option is
                ``backend_name``, which is required.
            params: Program parameters.
            callback: Callback function to be invoked for any interim results.

        Returns:
            A ``RuntimeJob`` instance representing the execution.
        """
        if 'backend_name' not in options:
            raise QiskitError('"backend_name" is required field in "options"')

        backend_name = options['backend_name']
        params_str = json.dumps(params, cls=RuntimeEncoder)
        response = self._api_client.program_run(program_id=program_id,
                                                credentials=self._provider.credentials,
                                                backend_name=backend_name,
                                                params=params_str)

        backend = self._provider.get_backend(backend_name)
        job = RuntimeJob(backend=backend, api_client=self._api_client,
                         job_id=response['id'], program_id=program_id, params=params,
                         user_callback=callback)
        return job

    def upload_program(
            self,
            name: str,
            data: Union[bytes, str],
    ) -> str:
        """Upload a runtime program.

        Args:
            name: Name of the program.
            data: Name of the program file or program data to upload.

        Returns:
            Program ID.
        """
        response = self._api_client.program_create(name, data)
        return response['id']

    def delete_program(self, program_id: str):
        """Delete a runtime program.

        Args:
            program_id: Program ID.
        """
        self._api_client.program_delete(program_id=program_id)

    def job(self, job_id: str):
        """Retrieve a runtime job.

        Args:
            job_id: Job ID.

        Returns:
            Runtime job retrieved.
        """
        response = self._api_client.program_job_get(job_id)
        backend = self._provider.get_backend(response['backend'])
        return RuntimeJob(backend=backend, api_client=self._api_client, job_id=response['id'],
                          program_id=response.get('program', ""),
                          params=response.get('params', {}))
