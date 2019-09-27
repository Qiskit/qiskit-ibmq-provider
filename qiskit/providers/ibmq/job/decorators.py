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

"""Decorators for job."""

from typing import Callable
from functools import wraps

from qiskit.providers import JobError


def requires_job_id(func: Callable):
    """Decorator that raises a JobError if the job does not have an ID,
    implying it was not submitted.

    Args:
        func (callable): function to be decorated.

    Returns:
        callable: the decorated function.
    """
    @wraps(func)
    def _wrapper(job, *args, **kwargs):
        if not job.job_id():
            raise JobError("The job has not been submitted!")

        return func(job, *args, **kwargs)

    return _wrapper
