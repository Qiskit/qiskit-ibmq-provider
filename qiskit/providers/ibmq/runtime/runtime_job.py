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

"""IBM Quantum Experience runtime job."""

from typing import Any, Optional, Callable, Dict
import time
import logging
import json
import asyncio
from concurrent import futures
import traceback
import queue

from qiskit.providers.exceptions import JobTimeoutError
from qiskit.providers.backend import Backend
from qiskit.providers.jobstatus import JobStatus, JOB_FINAL_STATES
from qiskit.providers.ibmq import ibmqbackend  # pylint: disable=unused-import

from .utils import RuntimeDecoder
from .constants import API_TO_JOB_STATUS
from .exceptions import RuntimeJobFailureError, RuntimeInvalidStateError
from ..api.clients import RuntimeClient, RuntimeWebsocketClient
from ..exceptions import IBMQError

logger = logging.getLogger(__name__)


class RuntimeJob:
    """Representation of a runtime program execution.

    A new ``RuntimeJob`` instance is returned when you call
    :meth:`qiskit.providers.ibmq.runtime.IBMRuntimeService.run`
    to execute a runtime program, and when you call
    :meth:`qiskit.providers.ibmq.runtime.IBMRuntimeService.job`
    to retrieve a previously executed job.

    If the program execution is successful, you can inspect the job's status by
    calling :meth:`status()`. Job status can be one of the
    :class:`~qiskit.providers.JobStatus` members.

    Some of the methods in this class are blocking, which means control may
    not be returned immediately. :meth:`result()` is an example
    of a blocking method::

        job = provider.runtime.run(...)

        try:
            job_result = job.result()  # It will block until the job finishes.
            print("The job finished with result {}".format(job_result))
        except IBMQJobFailureError as ex:
            print("Job failed!: {}".format(ex))

    If the program has any interim results, you can use the ``callback``
    parameter of the
    :meth:`~qiskit.providers.ibmq.runtime.IBMRuntimeService.run`
    method to stream the interim results.
    Alternatively, you can use the :meth:`stream_results` method to stream
    the results at a later time, but before the job finishes.
    """

    _executor = futures.ThreadPoolExecutor()

    def __init__(
            self,
            backend: 'ibmqbackend.IBMQBackend',
            api_client: RuntimeClient,
            ws_client: RuntimeWebsocketClient,
            job_id: str,
            program_id: str,
            params: Optional[Dict] = None,
            user_callback: Optional[Callable] = None
    ) -> None:
        """RuntimeJob constructor.

        Args:
            backend: The backend instance used to run this job.
            api_client: Object for connecting to the server.
            ws_client: Object for connecting to the server via websocket.
            job_id: Job ID.
            program_id: ID of the program this job is for.
            params: Job parameters.
            user_callback: User callback function.
        """
        self._job_id = job_id
        self._backend = backend
        self._api_client = api_client
        self._ws_client = ws_client
        self._results = None
        self._params = params or {}
        self._program_id = program_id
        self._status = JobStatus.INITIALIZING

        # Used for streaming
        self._streaming = False
        self._streaming_loop = None
        self._streaming_task = None
        self._result_queue = queue.Queue()

        if user_callback is not None:
            self.stream_results(user_callback)

    def result(
            self,
            timeout: Optional[float] = None,
            wait: float = 5
    ) -> Any:
        """Return the results of the job.

        If ``include_interim=True`` is specified, this method will return a
        list that includes both interim and final results in the order they
        were published by the program.

        Args:
            timeout: Number of seconds to wait for job.
            wait: Seconds between queries.

        Returns:
            Runtime job result.

        Raises:
            RuntimeJobFailureError: If the job failed.
        """
        if not self._results:
            self.wait_for_final_state(timeout=timeout, wait=wait)
            result_raw = self._api_client.job_results(job_id=self.job_id())
            if self._status == JobStatus.ERROR:
                raise RuntimeJobFailureError(f"Unable to retrieve result for job {self.job_id()}. "
                                             f"Job has failed:\n{result_raw}")
            self._results = self._decode_data(result_raw)
        return self._results

    def cancel(self) -> None:
        """Cancel the job."""
        self._api_client.job_cancel(self.job_id())
        self._cancel_result_streaming()
        self._status = JobStatus.CANCELLED

    def status(self) -> JobStatus:
        """Return the status of the job.

        Returns:
            Status of this job.

        Raises:
            IBMQError: If an unknown status is returned from the server.
        """
        if self._status not in JOB_FINAL_STATES:
            response = self._api_client.job_get(job_id=self.job_id())
            try:
                self._status = API_TO_JOB_STATUS[response['status'].upper()]
            except KeyError:
                raise IBMQError(f"Unknown status: {response['status']}")
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

    def stream_results(self, callback: Callable) -> None:
        """Start streaming job results.

        Args:
            callback: Callback function to be invoked for any interim results.
                The callback function will receive 2 position parameters:

                    1. Job ID
                    2. Job interim result.

        Raises:
            RuntimeInvalidStateError: If a callback function is already streaming results.
        """
        if self._streaming:
            raise RuntimeInvalidStateError("A callback function is already streaming results.")

        self._executor.submit(self._start_websocket_client,
                              result_queue=self._result_queue)
        self._executor.submit(self._stream_results,
                              result_queue=self._result_queue, user_callback=callback)

    def _cancel_result_streaming(self) -> None:
        """Cancel result streaming."""
        # TODO - consider making this public
        if not self._streaming:
            return
        self._streaming_loop.call_soon_threadsafe(self._streaming_task.cancel())

    def _start_websocket_client(
            self,
            result_queue: queue.Queue
    ) -> None:
        """Start websocket client to stream results.

        Args:
            result_queue: Queue used to pass messages.
        """
        try:
            # Need new loop for the thread.
            self._streaming_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._streaming_loop)
            # TODO - use asyncio.create_task() when 3.6 is dropped.
            self._streaming_task = self._streaming_loop.create_task(
                self._ws_client.job_results(self._job_id, result_queue))
            self._streaming = True

            logger.debug("Start websocket client for job %s", self.job_id())
            # loop.run_until_complete(self._ws_client.job_results(self._job_id, result_queue))
            self._streaming_loop.run_until_complete(self._streaming_task)
        except Exception:  # pylint: disable=broad-except
            logger.warning(
                "An error occurred while streaming results "
                "from the server for job %s:\n%s", self.job_id(), traceback.format_exc())
        finally:
            if self._streaming_loop is not None:
                self._streaming_loop.run_until_complete(self._ws_client.disconnect())
            self._streaming = False

    def _stream_results(self, result_queue: queue.Queue, user_callback: Callable) -> None:
        """Stream interim results.

        Args:
            result_queue: Queue used to pass websocket messages.
            user_callback: User callback function.
        """
        logger.debug("Start result streaming for job %s", self.job_id())
        while True:
            try:
                response = result_queue.get()
                if response == self._ws_client.POISON_PILL:
                    self._empty_result_queue(result_queue)
                    return
                user_callback(self.job_id(), self._decode_data(response))
            except Exception:  # pylint: disable=broad-except
                logger.warning(
                    "An error occurred while streaming results "
                    "for job %s:\n%s", self.job_id(), traceback.format_exc())

    def _empty_result_queue(self, result_queue: queue.Queue) -> None:
        """Empty the result queue.

        Args:
            result_queue: Result queue to empty.
        """
        try:
            while True:
                result_queue.get_nowait()
        except queue.Empty:
            pass

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
    def inputs(self) -> Dict:
        """Job input parameters.

        Returns:
            Input parameters used in this job.
        """
        return self._params

    @property
    def program_id(self) -> str:
        """Returns program ID.

        Returns:
            ID of the program this job is for.
        """
        return self._program_id
