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

"""Utility functions for the IBM Quantum Experience dashboard."""

from collections import namedtuple
from enum import Enum

from qiskit.providers.ibmq.runtime.runtime_job import RuntimeJob
from qiskit.providers.job import JobV1 as Job


class JobType(Enum):
    """The type of an executed job"""
    Circuit = 1
    Runtime = 2


def get_job_type(job: Job) -> JobType:
    """Get job type (JobType) for the Job object

    Args:
        job: the Job object

    Returns:
        JobType: the job type

    """
    # pylint: disable=unidiomatic-typecheck
    return JobType.Runtime if type(job) == RuntimeJob else JobType.Circuit


BackendWithProviders = namedtuple('BackendWithProviders', ['backend', 'providers'])
"""Named tuple used to pass a backend and its providers."""
