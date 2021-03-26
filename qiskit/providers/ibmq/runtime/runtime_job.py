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
import queue
from concurrent import futures

from qiskit.providers.job import JobV1 as Job
from qiskit.providers.jobstatus import JobStatus

from ..api.clients import RuntimeClient


class RuntimeJob(Job):

    _executor = futures.ThreadPoolExecutor()

    def __init__(
            self,
            backend: 'ibmqbackend.IBMQBackend',
            api_client: RuntimeClient,
            job_id: str,
            params: Dict,
            user_callback: Optional[Callable] = None
    ) -> None:
        """RuntimeJob constructor.

        Args:
            backend: The backend instance used to run this job.
            api_client: Object for connecting to the server.
            job_id: Job ID.
        """
        super().__init__(backend, job_id)
        self._api_client = api_client
        self._result = None
        self._params = params

        self._user_callback = user_callback

    def submit(self):
        """Unsupported method.

        Note:
            This method is not supported, please use
            :meth:`~qiskit.providers.ibmq.ibmqbackend.IBMQBackend.run`
            to submit a job.

        Raises:
            NotImplementedError: Upon invocation.
        """
        raise NotImplementedError("submit() is not supported. Please use "
                                  "IBMRuntimeService.run() to submit a runtime job.")

    def result(
            self,
            timeout: Optional[float] = None
    ) -> Any:
        """Return the results of the job."""
        if not self._result:
            self._result = self._api_client.program_job_results(job_id=self.job_id())
        return self._result

    def cancel(self):
        """Attempt to cancel the job."""
        raise NotImplementedError

    def status(self) -> JobStatus:
        """Return the status of the job."""
        response = self._api_client.program_job_get(job_id=self.job_id())
        status = response['status'].upper()
        if status == 'RUNNING':
            return JobStatus.RUNNING
        elif status == 'SUCCEEDED':
            return JobStatus.DONE
        elif status == 'PENDING':
            return JobStatus.INITIALIZING
        else:
            return JobStatus.ERROR

    @property
    def parameters(self) -> Dict:
        return self._params
