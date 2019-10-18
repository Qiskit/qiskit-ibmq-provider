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

from ..job.ibmqjob import IBMQJob


class ManagedJob:
    """Job managed by job manager."""

    def __init__(
            self,
            experiments: Union[List[QuantumCircuit], List[Schedule]],
            start_index: Optional[int] = None,
            future: Optional[Future] = None,
            job: Optional[IBMQJob] = None
    ):
        """Creates a new ManagedJob instance.

        Args:
            experiments: Experiments for the job.
            start_index: Starting index of the experiment set.
            future: Job submit future.
            job: Job being managed.
        """
        self.experiments = experiments
        self.start_index = start_index if start_index is not None else 'N/A'
        self.end_index = start_index + len(experiments) - 1 if start_index is not None else 'N/A'
        self.future = future
        self.job = job

    def submit_result(self) -> None:
        """Collect job submit result."""
        try:
            self.job = self.future.result()
        except Exception as err:  # pylint: disable=broad-except
            warnings.warn("Unable to submit job for experiments {}-{}: {}".format(
                self.start_index, self.end_index, err))

        self.future = None
