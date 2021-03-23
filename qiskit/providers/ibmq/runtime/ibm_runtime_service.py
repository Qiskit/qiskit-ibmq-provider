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
from typing import Dict, Callable, Optional, Union
import queue
from concurrent import futures
import json

from qiskit.providers.ibmq import accountprovider  # pylint: disable=unused-import
from qiskit import QiskitError

from .runtime_job import RuntimeJob
from .runtime_program import RuntimeProgram
from ..utils.runtime import RuntimeEncoder
from ..api.clients.runtime import RuntimeClient

logger = logging.getLogger(__name__)


class IBMRuntimeService:
    """IBM Quantum runtime service."""

    _executor = futures.ThreadPoolExecutor()

    def __init__(self, provider: 'accountprovider.AccountProvider', access_token: str) -> None:
        """IBMRuntimeService constructor.

        Args:
            provider: IBM Quantum account provider.
            access_token: IBM Quantum access token.
        """
        self._provider = provider
        self._api_client = RuntimeClient(access_token, provider.credentials)
        self._programs = {}

    def programs(self):
        if not self._programs:
            self._get_programs()

        for prog in self._programs.values():
            print("="*50)
            prog.pprint()

    def _get_programs(self):
        response = self._api_client.list_programs()
        for prog_dict in response:
            kwargs = {}
            if 'cost' in prog_dict:
                kwargs['cost'] = prog_dict['cost']
            if 'data' in prog_dict:
                kwargs['data'] = prog_dict['data']
            program = RuntimeProgram(program_name=prog_dict['name'],
                                     program_id=prog_dict['id'],
                                     description=prog_dict.get('description', ""),
                                     parameters=prog_dict.get('parameters', None),
                                     return_values=prog_dict.get('return_values', None),
                                     **kwargs)
            self._programs[program.name] = program

    def program(self, program_name: str):
        if not self._programs:
            self._get_programs()

        if program_name in self._programs:
            self._programs[program_name].pprint()
        else:
            raise ValueError(f"Program {program_name} is not found.")

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
        # interim_queue = queue.Queue() if callback else None
        params_str = json.dumps(params, cls=RuntimeEncoder)
        response = self._api_client.program_run(program_id=program_id,
                                                credentials=self._provider.credentials,
                                                backend_name=backend_name,
                                                params=params_str)
        backend = self._provider.get_backend(backend_name)
        job = RuntimeJob(backend=backend, api_client=self._api_client, job_id=response['id'],
                         user_callback=callback)
        return job

    def upload(
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

    def job(self, program_id: str, job_id: str):
        response = self._api_client.program_job_get(program_id, job_id)
        print(f">>>>>> response is {response}")
