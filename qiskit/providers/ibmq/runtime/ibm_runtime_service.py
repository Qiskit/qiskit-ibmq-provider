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
from typing import Dict, Callable, Optional
import queue
from concurrent import futures

from qiskit.providers.ibmq import accountprovider  # pylint: disable=unused-import

from .runtime_job import RuntimeJob
from .runtime_program import RuntimeProgram
from ..ibmqbackend import IBMQBackend
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
        response = self._api_client.list_programs()
        for prog_dict in response:
            kwargs = {}
            if 'cost' in prog_dict:
                kwargs['cost'] = prog_dict['cost']
            if 'data' in prog_dict:
                kwargs['data'] = prog_dict['data']
            program = RuntimeProgram(program_name=prog_dict['name'],
                                     program_id=prog_dict['id'],
                                     description=prog_dict['description'],
                                     parameters=prog_dict['parameters'],
                                     return_values=prog_dict['return_values'],
                                     **kwargs)
            self._programs[program.name] = program
        for prog in self._programs.values():
            prog.pprint()

    def program(self, program_name: str):
        if program_name in self._programs:
            self._programs[program_name].pprint()
        else:
            program = RuntimeProgram(**self._api_client.program_get(program_name))
            self._programs[program.name] = program
            program.pprint()

    def run(
            self,
            program_name: str,
            backend: IBMQBackend,
            params: Dict,
            callback: Optional[Callable] = None
    ) -> RuntimeJob:
        interim_queue = queue.Queue() if callback else None
        response = self._api_client.program_run(program_id=program_name,
                                                credentials=self._provider.credentials,
                                                backend_name=backend.name(),
                                                params=params, interim_queue=interim_queue)
        job = RuntimeJob(backend=backend, api_client=self._api_client, job_id=response['id'],
                         interim_queue=interim_queue, user_callback=callback)
        return job
