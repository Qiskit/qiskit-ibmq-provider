# -*- coding: utf-8 -*-

# This code is part of Qiskit.
#
# (C) Copyright IBM 2019, 2020.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Experiments managed by the job manager."""

import warnings
import logging
from typing import List, Optional
from concurrent.futures import ThreadPoolExecutor

from qiskit.providers.ibmq import IBMQBackend
from qiskit.qobj import Qobj
from qiskit.result import Result
from qiskit.providers.jobstatus import JobStatus
from qiskit.providers.exceptions import JobError
from qiskit.providers.ibmq.apiconstants import ApiJobShareLevel

from ..job.ibmqjob import IBMQJob
from ..job.exceptions import IBMQJobTimeoutError

logger = logging.getLogger(__name__)


class ManagedJob:
    """Job managed by job manager."""

    def __init__(
            self,
            start_index: int,
            experiments_count: int,
            job: Optional[IBMQJob] = None
    ):
        """Creates a new ManagedJob instance.

        Args:
            start_index: Starting index of the experiment set.
            experiments_count: Number of experiments.
            job: Job to be managed, or ``None`` if not already known. Default: None.
        """
        self.start_index = start_index
        self.end_index = start_index + experiments_count - 1
        self.future = None

        # Properties that may be populated by the future.
        self.job = job  # type: Optional[IBMQJob]
        self.submit_error = None  # type: Optional[Exception]

    def submit(
            self,
            qobj: Qobj,
            job_name: str,
            backend: IBMQBackend,
            executor: ThreadPoolExecutor,
            job_share_level: ApiJobShareLevel,
            job_tags: Optional[List[str]] = None
    ) -> None:
        """Submit the job.

        Args:
            qobj: Qobj to run.
            job_name: Name of the job.
            backend: Backend to execute the experiments on.
            executor: The thread pool to use.
            job_share_level: Job share level.
            job_tags: tags to be assigned to the job.
        """

        # Submit the job in its own future.
        self.future = executor.submit(
            self._async_submit, qobj=qobj, job_name=job_name, backend=backend,
            job_share_level=job_share_level, job_tags=job_tags)

    def _async_submit(
            self,
            qobj: Qobj,
            job_name: str,
            backend: IBMQBackend,
            job_share_level: ApiJobShareLevel,
            job_tags: Optional[List[str]] = None
    ) -> None:
        """Run a Qobj asynchronously and populate instance attributes.

        Args:
            qobj: Qobj to run.
            job_name: Name of the job.
            backend: Backend to execute the experiments on.
            job_share_level: Job share level.
            job_tags: tags to be assigned to the job.

        Returns:
            IBMQJob instance for the job.
        """
        try:
            self.job = backend.run(
                qobj=qobj,
                job_name=job_name,
                job_share_level=job_share_level.value,
                job_tags=job_tags)
        except Exception as err:  # pylint: disable=broad-except
            warnings.warn("Unable to submit job for experiments {}-{}: {}".format(
                self.start_index, self.end_index, err))
            self.submit_error = err

    def status(self) -> Optional[JobStatus]:
        """Query the API for job status.

        Returns:
            Current job status, or ``None`` if an error occurred.
        """
        if self.submit_error is not None:
            return None

        if self.job is None:
            # Job not yet submitted
            return JobStatus.INITIALIZING

        try:
            return self.job.status()
        except JobError as err:
            warnings.warn(
                "Unable to retrieve job status for experiments {}-{}, job ID={}: {} ".format(
                    self.start_index, self.end_index, self.job.job_id(), err))

        return None

    def result(
            self,
            timeout: Optional[float] = None,
            partial: bool = False
    ) -> Optional[Result]:
        """Return the result of the job.

        Args:
           timeout: number of seconds to wait for job
           partial: If true, attempt to retrieve partial job results.

        Returns:
            Result object or ``None`` if result could not be retrieved.

        Raises:
            IBMQJobTimeoutError: if the job does not return results before a
                specified timeout.
        """
        result = None
        if self.job is not None:
            try:
                result = self.job.result(timeout=timeout, partial=partial)
            except IBMQJobTimeoutError:
                raise
            except JobError as err:
                warnings.warn(
                    "Unable to retrieve job result for experiments {}-{}, job ID={}: {} ".format(
                        self.start_index, self.end_index, self.job.job_id(), err))

        return result

    def error_message(self) -> Optional[str]:
        """Provide details about the reason of failure.

        Returns:
            An error report if the job failed or ``None`` otherwise.
        """
        if self.job is None:
            return None
        try:
            return self.job.error_message()
        except JobError:
            return "Unknown error."

    def cancel(self) -> None:
        """Attempt to cancel a job."""
        cancelled = False
        cancel_error = "Unknown error"
        try:
            cancelled = self.job.cancel()
        except JobError as err:
            cancel_error = str(err)

        if not cancelled:
            logger.warning("Unable to cancel job %s for experiments %d-%d: %s",
                           self.job.job_id(), self.start_index, self.end_index, cancel_error)

    def qobj(self) -> Optional[Qobj]:
        """Return the Qobj for this job.

        Returns:
            The Qobj for this job or ``None`` if the Qobj could not be retrieved.
        """
        if self.job is None:
            return None
        try:
            return self.job.qobj()
        except JobError as err:
            warnings.warn(
                "Unable to retrieve qobj for experiments {}-{}, job ID={}: {} ".format(
                    self.start_index, self.end_index, self.job.job_id(), err))

        return None
