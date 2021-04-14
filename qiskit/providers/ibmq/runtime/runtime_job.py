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
import queue

from qiskit.exceptions import QiskitError
from qiskit.providers.exceptions import JobTimeoutError
from qiskit.providers.backend import Backend
from qiskit.providers.jobstatus import JobStatus, JOB_FINAL_STATES

from .utils import RuntimeDecoder
from .constants import API_TO_JOB_STATUS
from ..api.clients import RuntimeClient, RuntimeWebsocketClient
from ..job.exceptions import IBMQJobFailureError

logger = logging.getLogger(__name__)


class RuntimeJob:
    """Representation of a runtime program execution."""

    _executor = futures.ThreadPoolExecutor()
    _result_queue_poison_pill = "_poison_pill"

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
        # self._user_callback = user_callback
        self._program_id = program_id
        self._status = JobStatus.INITIALIZING
        self._streaming = False
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
            IBMQJobFailureError: If the job failed.
        """
        if not self._results:
            self.wait_for_final_state(timeout=timeout, wait=wait)
            result_raw = self._api_client.job_results(job_id=self.job_id())
            if self._status == JobStatus.ERROR:
                raise IBMQJobFailureError(f"Unable to retrieve result for job {self.job_id()}. "
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
        """
        if self._status not in JOB_FINAL_STATES:
            response = self._api_client.job_get(job_id=self.job_id())
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

    def stream_results(self, callback: Callable) -> None:
        """Start streaming job results.

        Args:
            callback: Callback function to be invoked for any interim results.
                The callback function will receive 2 position parameters:
                    1. Job ID
                    2. Job interim result.
        """
        if self._streaming:
            raise QiskitError("A callback function is already streaming results.")
        self._streaming = True

        self._executor.submit(self._start_websocket_client,
                              result_queue=self._result_queue)
        self._executor.submit(self._stream_results,
                              result_queue=self._result_queue, user_callback=callback)
        # TODO - wait for ws to connect before returning?

    def _cancel_result_streaming(self) -> None:
        """Cancel result streaming."""
        if not self._streaming:
            return
        self._result_queue.put_nowait(self._result_queue_poison_pill)

    def _start_websocket_client(
            self,
            result_queue: queue.Queue
    ) -> None:
        """Start websocket client to stream results."""
        loop = None
        try:
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError as ex:
                # Event loop may not be set in a child thread.
                if 'There is no current event loop' in str(ex):
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                else:
                    logger.warning(f"Unable to get the event loop: {ex}")
                    raise

            logger.debug(f"Start websocket client for job {self.job_id()}")
            loop.run_until_complete(self._ws_client.job_results(self._job_id, result_queue))
        except Exception:  # pylint: disable=broad-except
            logger.warning(
                f"An error occurred while streaming results "
                f"from the server for job {self.job_id()}:\n{traceback.format_exc()}")
        finally:
            result_queue.put_nowait(self._result_queue_poison_pill)
            if loop is not None:
                loop.run_until_complete(self._ws_client.disconnect())

    def _stream_results(self, result_queue: queue.Queue, user_callback: Callable) -> None:
        """Stream interim results.

        Args:
            user_callback: User callback function.
        """
        logger.debug(f"Start result streaming for job {self.job_id()}")
        while True:
            try:
                response = result_queue.get()
                if response == self._result_queue_poison_pill:
                    self._empty_result_queue(result_queue)
                    self._streaming = False
                    return
                user_callback(self.job_id(), self._decode_data(response))
            except Exception:  # pylint: disable=broad-except
                logger.warning(
                    f"An error occurred while streaming results "
                    f"for job {self.job_id()}:\n{traceback.format_exc()}")

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
