# -*- coding: utf-8 -*-

# This code is part of Qiskit.
#
# (C) Copyright IBM 2020.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""IBM Quantum Experience job."""

import logging
from typing import Optional, Dict, List
import time

from qiskit.providers.jobstatus import JobStatus, JOB_FINAL_STATES
from qiskit.providers.exceptions import JobTimeoutError

from ..api.clients.random import RandomClient
from ..utils.utils import api_status_to_job_status
from .utils import bytes_to_bitarray

logger = logging.getLogger(__name__)


class CQCExtractorJob:
    """Representation of an asynchronous call to the CQC extractor.

    An instance of this class is returned when you call
    :meth:`~qiskit.providers.ibmq.random.CQCExtractor.run_async_ext1`,
    :meth:`~qiskit.providers.ibmq.random.CQCExtractor.run_async_ext2`, or
    :meth:`~qiskit.providers.ibmq.random.CQCExtractor.retrieve_job` method of the
    :class:`~qiskit.providers.ibmq.random.CQCExtractor` class.

    If the job is successfully submitted, you can inspect the job's status by
    calling :meth:`status()`.

    Some of the methods in this class are blocking, which means control may
    not be returned immediately. :meth:`block_until_ready()` is an example
    of a blocking method, which waits until the job completes::

        job = extractor.run_async_ext1(...)
        random_bits = job.block_until_ready()

    Note:
        An error may occur when querying the remote server to get job information.
        The most common errors are temporary network failures
        and server errors, in which case an
        :class:`~qiskit.providers.ibmq.api.exceptions.RequestsApiError`
        is raised. These errors usually clear quickly, so retrying the operation is
        likely to succeed.
    """

    def __init__(
            self,
            job_id: str,
            client: RandomClient,
            parameters: Optional[Dict] = None,
    ) -> None:
        """CQCExtractorJob constructor.

        Args:
            job_id: Job ID.
            client: Object for connecting to the server.
            parameters: Parameters used for this job.
        """
        self.job_id = job_id
        self._client = client
        self._parameters = parameters
        self._result_url = None  # type: Optional[str]
        self._result = None  # type: Optional[List[int]]
        self._status = None
        self._api_parameters = None

    def status(self) -> JobStatus:
        """Query the server for the latest job status.

        Returns:
            The status of the job.
        """
        if self._status not in JOB_FINAL_STATES:
            self._refresh()
        return self._status

    def block_until_ready(
            self,
            timeout: Optional[float] = None,
            wait: float = 10
    ) -> List[int]:
        """Wait for the job to finish and return the result.

        Args:
            timeout: Seconds to wait for the job. If ``None``, wait indefinitely.
            wait: Seconds between queries. Use a larger number if the job is
                expected to run for a long time.

        Returns:
            Extractor output.

        Raises:
            JobTimeoutError: If the job does not finish before the
                specified timeout.
        """
        if self._result:
            return self._result

        self._wait_for_final_state(timeout, wait)
        raw_bytes = self._client.get_object_storage(self._result_url)
        if self.extractor_method == 'ext1':
            self._result = bytes_to_bitarray(raw_bytes, self.parameters['ext1_output_num_bits'])
        else:
            self._result = bytes_to_bitarray(
                raw_bytes,
                (self.parameters['ext2_wsr_multiplier']-1)*self.parameters['ext2_seed_num_bits'])

        return self._result

    @property
    def extractor_method(self) -> str:
        """Return the extractor method used.

        Returns:
            Extractor method used.
        """
        if not self._api_parameters:
            self._refresh()
        if set(self._api_parameters.keys()) == {'n', 'm', 'x', 'y'}:
            return 'ext1'
        return 'ext2'

    @property
    def parameters(self) -> Dict:
        """Return the parameters passed to the extractor.

        Returns:
            Parameters passed to the extractor.
        """
        if self._parameters:
            return self._parameters

        if not self._api_parameters:
            self._refresh()

        if self.extractor_method == 'ext1':
            self._parameters = {
                'ext1_input_num_bits': self._api_parameters['n'],
                'ext1_output_num_bits': self._api_parameters['m'],
                'ext1_raw_bytes': self._client.get_object_storage(self._api_parameters['x']),
                'ext1_wsr_bytes': self._client.get_object_storage(self._api_parameters['y'])
            }
        else:
            self._parameters = {
                'ext2_seed_num_bits': self._api_parameters['a'],
                'ext2_wsr_multiplier': self._api_parameters['b'],
                'ext2_seed_bytes': self._client.get_object_storage(self._api_parameters['r']),
                'ext2_wsr': self._client.get_object_storage(self._api_parameters['x'])
            }

        return self._parameters

    def _refresh(self) -> None:
        """Retrieve job data from the remote server."""
        response = self._client.job_get(self.job_id)
        self._status = api_status_to_job_status(response['status'])
        if not self._api_parameters:
            self._api_parameters = response['parameters']
        if self._status == JobStatus.DONE:
            self._result_url = response['result']

    def _wait_for_final_state(
            self,
            timeout: Optional[float] = None,
            wait: float = 30
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
                    'Timeout while waiting for job {}.'.format(self.job_id))
            time.sleep(wait)
            status = self.status()
