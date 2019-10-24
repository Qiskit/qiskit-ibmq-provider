# -*- coding: utf-8 -*-

# This code is part of Qiskit.
#
# (C) Copyright IBM 2019.
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
from typing import List, Optional, Union
from concurrent.futures import Future

from qiskit.circuit import QuantumCircuit
from qiskit.pulse import Schedule
from qiskit.result import Result
from qiskit.providers.jobstatus import JobStatus
from qiskit.providers.exceptions import JobError, JobTimeoutError

from ..job.ibmqjob import IBMQJob


class ManagedJob:
    """Job managed by job manager."""

    def __init__(
            self,
            experiments: Union[List[QuantumCircuit], List[Schedule]],
            start_index: int,
            future: Future
    ):
        """Creates a new ManagedJob instance.

        Args:
            experiments: Experiments for the job.
            start_index: Starting index of the experiment set.
            future: Job submit future.
        """
        self.experiments = experiments
        self.start_index = start_index
        self.end_index = start_index + len(experiments) - 1
        self.future = future
        self.job = None  # type: Optional[IBMQJob]
        self.submit_error = None  # type: Optional[Exception]

    def submit_result(self) -> None:
        """Collect job submit result."""
        try:
            self.job = self.future.result()
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

    def result(self, timeout: Optional[float] = None) -> Result:
        """Return the result of the job.

        Args:
           timeout: number of seconds to wait for job

        Returns:
            Result object

        Raises:
            JobTimeoutError: if the job does not return results before a
                specified timeout.
        """
        result = None
        if self.job is not None:
            try:
                # TODO Revise this when partial result is supported
                result = self.job.result(timeout=timeout)
            except JobTimeoutError:
                raise
            except JobError as err:
                warnings.warn(
                    "Unable to retrieve job result for experiments {}-{}, job ID={}: {} ".format(
                        self.start_index, self.end_index, self.job.job_id(), err))

        return result
