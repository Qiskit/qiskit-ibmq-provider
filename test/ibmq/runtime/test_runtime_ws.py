# This code is part of Qiskit.
#
# (C) Copyright IBM 2018, 2019.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Test for the Websocket client."""

import sys
import asyncio
import warnings
from contextlib import suppress
import queue
import time
from concurrent.futures import ThreadPoolExecutor
import threading

import websockets

from qiskit.providers.ibmq.api.clients.runtime_ws import RuntimeWebsocketClient
from qiskit.providers.ibmq.runtime import RuntimeJob
from qiskit.test.mock.fake_qasm_simulator import FakeQasmSimulator

from ...ibmqtestcase import IBMQTestCase
from .websocket_server import (websocket_handler, JOB_ID_PROGRESS_DONE, JOB_ID_ALREADY_DONE,
                               JOB_ID_RETRY_SUCCESS, JOB_ID_RETRY_FAILURE, JOB_ID_RANDOM_CODE,
                               JOB_PROGRESS_RESULT_COUNT)
from .fake_runtime_client import BaseFakeRuntimeClient, TimedRuntimeJob


class TestRuntimeWebsocketClient(IBMQTestCase):
    """Tests for the the websocket client against a mock server."""

    TEST_IP_ADDRESS = '127.0.0.1'
    INVALID_PORT = 9876
    VALID_PORT = 8765
    VALID_URL = f"ws://{TEST_IP_ADDRESS}:{VALID_PORT}"

    _executor = ThreadPoolExecutor()

    @classmethod
    def setUpClass(cls):
        """Initial class level setup."""
        super().setUpClass()

        # Launch the mock server.
        # start_server = websockets.serve(websocket_handler, cls.TEST_IP_ADDRESS, cls.VALID_PORT)
        # cls.server = asyncio.get_event_loop().run_until_complete(start_server)
        cls._ws_event = threading.Event()

    @classmethod
    def _ws_server(cls):
        loop = asyncio.get_event_loop()
        start_server = websockets.serve(websocket_handler, cls.TEST_IP_ADDRESS, cls.VALID_PORT)
        cls.server = asyncio.get_event_loop().run_until_complete(start_server)
        cls._ws_event.wait(timeout=10)


    @classmethod
    def tearDownClass(cls):
        """Class level cleanup."""
        super().tearDownClass()

        # Close the mock server.
        loop = asyncio.get_event_loop()
        cls.server.close()
        loop.run_until_complete(cls.server.wait_closed())

        with warnings.catch_warnings():
            # Suppress websockets deprecation warning
            warnings.filterwarnings("ignore", category=PendingDeprecationWarning)
            warnings.filterwarnings("ignore", category=DeprecationWarning)
            # Manually cancel any pending asyncio tasks.
            if sys.version_info[0:2] < (3, 9):
                pending = asyncio.Task.all_tasks()
            else:
                pending = asyncio.all_tasks(loop)
        for task in pending:
            task.cancel()
            try:
                with suppress(asyncio.CancelledError):
                    loop.run_until_complete(task)
            except Exception as err:  # pylint: disable=broad-except
                cls.log.error("An error %s occurred canceling task %s. "
                              "Traceback:", str(err), str(task))
                task.print_stack()

    def test_interim_result_callback(self):
        """Test interim result callback."""
        def result_callback(job_id, interim_result):
            print(f">>>>> callback called")
            nonlocal results
            results.append(interim_result)
            self.assertEqual(JOB_ID_PROGRESS_DONE, job_id)

        results = []
        # ws = RuntimeWebsocketClient(self.VALID_URL, "my_token")
        ws = RuntimeWebsocketClient('ws://{}:{}'.format(
            self.TEST_IP_ADDRESS, self.VALID_PORT), "foo")
        # api = BaseFakeRuntimeClient(job_classes=TimedRuntimeJob,
        #                             job_kwargs={"run_time": JOB_PROGRESS_RESULT_COUNT+2})
        job = RuntimeJob(backend=FakeQasmSimulator(),
                         api_client=BaseFakeRuntimeClient(),
                         ws_client=ws,
                         job_id=JOB_ID_PROGRESS_DONE,
                         program_id="my-program",
                         user_callback=result_callback)
        time.sleep(JOB_PROGRESS_RESULT_COUNT+2)
        self.assertEqual(JOB_PROGRESS_RESULT_COUNT, len(results))
        self.assertIsNone(job._ws_client._ws)

    def test_stream_results(self):
        pass

    def test_cancel_streaming(self):
        pass

    def test_completed_job(self):
        pass

    def test_websocket_retry_success(self):
        pass

    def test_websocket_retry_failure(self):
        pass

    def test_job_interim_results(self):
        """Test retrieving a job already in final status."""
        client = RuntimeWebsocketClient('ws://{}:{}'.format(
            self.TEST_IP_ADDRESS, self.VALID_PORT), "foo")

        asyncio.get_event_loop().run_until_complete(
            client.job_results(JOB_ID_PROGRESS_DONE, queue.Queue()))
