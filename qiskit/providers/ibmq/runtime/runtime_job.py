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
import json
import asyncio
from concurrent import futures
import traceback
import os

from qiskit.providers.exceptions import JobTimeoutError
from qiskit.providers.backend import Backend
from qiskit.providers.jobstatus import JobStatus, JOB_FINAL_STATES

from .utils import RuntimeDecoder
from .constants import API_TO_JOB_STATUS
from ..api.clients import RuntimeClient, RuntimeWebsocketClient
from ..api.exceptions import WebsocketTimeoutError
from ..job.exceptions import IBMQJobFailureError

logger = logging.getLogger(__name__)


class RuntimeJob:
    """Representation of a runtime program execution."""

    _executor = futures.ThreadPoolExecutor()

    def __init__(
            self,
            backend: 'ibmqbackend.IBMQBackend',
            api_client: RuntimeClient,
            access_token: str,
            job_id: str,
            program_id: str,
            params: Optional[Dict] = None,
            user_callback: Optional[Callable] = None
    ) -> None:
        """RuntimeJob constructor.

        Args:
            backend: The backend instance used to run this job.
            api_client: Object for connecting to the server.
            access_token: IBM Quantum Experience access token.
            job_id: Job ID.
            program_id: ID of the program this job is for.
            params: Job parameters.
            user_callback: User callback function.
        """
        self._job_id = job_id
        self._backend = backend
        self._api_client = api_client
        url = os.getenv('NTC_URL', "")
        ws_url = url.replace('https', 'wss')
        self._ws_client = RuntimeWebsocketClient(ws_url, access_token)
        self._results = []
        self._params = params or {}
        # self._user_callback = user_callback
        self._program_id = program_id
        self._status = JobStatus.INITIALIZING

        if user_callback is not None:
            self.stream_results(user_callback)

    def result(
            self,
            timeout: Optional[float] = None,
            wait: float = 5,
            include_interim: bool = False
    ) -> Any:
        """Return the results of the job.

        If ``include_interim=True`` is specified, this method will return a
        list that includes both interim and final results in the order they
        were published by the program.

        Args:
            timeout: Number of seconds to wait for job.
            wait: Seconds between queries.
            include_interim: Whether to include interim results.

        Returns:
            Runtime job result.

        Raises:
            IBMQJobFailureError: If the job failed.
        """
        if not self._results:
            self.wait_for_final_state(timeout=timeout, wait=wait)
            result_raw = self._api_client.program_job_results(job_id=self.job_id())
            if self._status == JobStatus.ERROR:
                raise IBMQJobFailureError(f"Unable to retrieve result for job {self.job_id()}. "
                                          f"Job has failed:\n{result_raw}")
            # TODO - Update when interim results are for streaming only
            result_list = result_raw.split('\n')
            for res in result_list:
                if not res:
                    continue
                self._results.append(self._decode_data(res))
        if include_interim:
            return self._results
        return self._results[-1]

    def cancel(self):
        """Attempt to cancel the job."""
        raise NotImplementedError

    def status(self) -> JobStatus:
        """Return the status of the job.

        Returns:
            Status of this job.
        """
        if self._status not in JOB_FINAL_STATES:
            response = self._api_client.program_job_get(job_id=self.job_id())
            self._status = API_TO_JOB_STATUS[response['status'].upper()]
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

    def stream_results(self, callback: Callable):
        """Start streaming job results.

        Args:
            callback: Callback function to be invoked for any interim results.
                The callback function will receive 2 position parameters:
                    1. Job ID
                    2. Job interim result.
        """
        self._executor.submit(self._stream_results, user_callback=callback)

    def _stream_results(self, user_callback: Callable) -> None:
        """Stream interim results.

        Args:
            user_callback: User callback function.
        """
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError as ex:
            # Event loop may not be set in a child thread.
            if 'There is no current event loop' in str(ex):
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            else:
                raise

        logger.debug(f"Start result streaming for job {self.job_id()}")
        try:
            while True:
                try:
                    response = loop.run_until_complete(self._ws_client.job_results(self._job_id))
                    user_callback(self.job_id(), self._decode_data(response))
                except WebsocketTimeoutError:
                    if self.status() in JOB_FINAL_STATES:
                        logger.debug(f"Job {self.job_id()} finished, stop result streaming.")
                        return
        except Exception:  # pylint: disable=broad-except
            logger.warning(
                f"An error occurred while streaming results for job {self.job_id()}: " +
                traceback.format_exc())
        finally:
            loop.run_until_complete(self._ws_client.disconnect())

    def _decode_data(self, data: Any) -> Any:
        """Attempt to decode data using default decoder.

        Args:
            data: Data to be decoded.

        Returns:
            Decoded data, or the original data if decoding failed.
        """
        try:
            return json.loads(data, cls=RuntimeDecoder)
        except json.JSONDecodeError:
            return data

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
