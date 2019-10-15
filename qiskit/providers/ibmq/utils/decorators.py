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

"""General decorator functions."""

from typing import Callable, Any
from functools import wraps

from qiskit.providers.exceptions import JobError


def requires_submit(func: Callable) -> Callable:
    """Decorator used by JobManager to wait for all jobs to be submitted.

    Args:
        func (callable): function to be decorated.

    Returns:
        callable: the decorated function.
    """
    @wraps(func)
    def _wrapper(
            job_mgr: 'JobManager',  # type: ignore[name-defined]
            *args: Any,
            **kwargs: Any
    ) -> Any:
        """Wrapper function.

        Args:
            job_mgr: JobManager instance used to manage the jobs.
            args: arguments to be passed to the decorated function.
            kwargs: keyword arguments to be passed to the decorated function.

        Returns:
            return value of the decorated function.

        Raises:
            JobError: if an error occurred while submitting jobs.
        """
        if job_mgr._future is None:
            raise JobError("Jobs need to be submitted first!")

        job_mgr._future.result()
        if job_mgr._future_captured_exception:
            raise JobError("Failed to submit jobs. " + job_mgr._future_error_msg) \
                from job_mgr._future_captured_exception

        return func(job_mgr, *args, **kwargs)

    return _wrapper
