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

"""IBM Quantum Experience Runtime job."""

from typing import Any, Optional, Callable, Dict
import time
import logging

from qiskit.providers.exceptions import JobTimeoutError
from qiskit.providers.backend import Backend

from ..api.clients import RuntimeClient
from .constants import JOB_FINAL_STATES

logger = logging.getLogger(__name__)


class RuntimeJob:

    def __init__(
            self,
            backend: 'ibmqbackend.IBMQBackend',
            api_client: RuntimeClient,
            job_id: str,
            program_id: str,
            params: Optional[Dict] = None,
            user_callback: Optional[Callable] = None
    ) -> None:
        """RuntimeJob constructor.

        Args:
            backend: The backend instance used to run this job.
            api_client: Object for connecting to the server.
            job_id: Job ID.
            program_id: ID of the program this job is for.
            params: Job parameters.
            user_callback: User callback function.
        """
        self._job_id = job_id
        self._backend = backend
        self._api_client = api_client
        self._result = None
        self._params = params or {}
        self._user_callback = user_callback
        self._program_id = program_id
        self._status = 'PENDING'

    def result(
            self,
            timeout: Optional[float] = None,
            wait: float = 5
    ) -> Any:
        """Return the results of the job.

        Args:
            timeout: Number of seconds to wait for job.
            wait: Seconds between queries.

        Returns:
            Runtime job result.
        """
        if not self._result:
            self.wait_for_final_state(timeout=timeout, wait=wait)
            self._result = self._api_client.program_job_results(job_id=self.job_id())
        return self._result

    def cancel(self):
        """Attempt to cancel the job."""
        raise NotImplementedError

    def status(self) -> str:
        """Return the status of the job.

        Returns:
            Status of this job.
        """
        if self._status not in JOB_FINAL_STATES:
            response = self._api_client.program_job_get(job_id=self.job_id())
            self._status = response['status'].upper()
        return self._status

    def wait_for_final_state(
            self,
            timeout: Optional[float] = None,
            wait: float = 5
    ) -> None:
        """Poll the job status until it progresses to a final state such as ``DONE`` or ``ERROR``.

        Args:
            timeout: Seconds to wait for the job. If ``None``, wait indefinitely.
            wait: Seconds between queries.

        Raises:
            JobTimeoutError: If the job does not reach a final state before the
                specified timeout.
        """
        start_time = time.time()
        status = self.status()
        while status not in JOB_FINAL_STATES:
            elapsed_time = time.time() - start_time
            if timeout is not None and elapsed_time >= timeout:
                raise JobTimeoutError(
                    'Timeout while waiting for job {}.'.format(self.job_id()))
            time.sleep(wait)
            status = self.status()
        return

    def job_id(self) -> str:
        """Return a unique id identifying the job.

        Returns:
            Job ID.
        """
        return self._job_id

    def backend(self) -> Backend:
        """Return the backend where this job was executed.

        Returns:
            Backend used for the job.
        """
        return self._backend

    @property
    def parameters(self) -> Dict:
        """Job parameters.

        Returns:
            Parameters used in this job.
        """
        return self._params

    @property
    def program_id(self) -> str:
        """Returns program ID.

        Returns:
            ID of the program this job is for.
        """
        return self._program_id
