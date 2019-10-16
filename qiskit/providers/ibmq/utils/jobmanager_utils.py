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

"""Utility functions for IBMQJobManager."""

from typing import Callable, Any, List, Optional, Union
from functools import wraps
from datetime import datetime

from qiskit.qobj import Qobj

from ..ibmqbackend import IBMQBackend
from ..job import IBMQJob
from ..exceptions import IBMQJobManagerSubmitError


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
            IBMQJobManagerSubmitError: if an error occurred while submitting jobs.
        """
        if not job_mgr._submit_called:
            raise IBMQJobManagerSubmitError("Jobs need to be submitted first!")

        job_mgr._submit_done_event.wait()
        if job_mgr._submit_exception:
            raise job_mgr._submit_exception

        return func(job_mgr, *args, **kwargs)

    return _wrapper


def submit_async(
        qobjs: List[Qobj],
        backend: IBMQBackend,
        name_prefix: Optional[str] = None
) -> List[Union[IBMQJob, IBMQJobManagerSubmitError]]:
    """Submit jobs to IBM Q asynchronously.

    Args:
        qobjs: A list of qobj's to run.
        backend: Backend to execute the experiments on.
        name_prefix: Prefix of the job name.

    Returns:
        A list of job submit results. Each entry is either ``IBMQJob`` if the
            submit was successful, or ``IBMQJobManagerSubmitError`` otherwise.
    """
    name_prefix = name_prefix or datetime.utcnow().isoformat()
    start_index = 0
    end_index = 0
    jobs = []
    try:
        for i, qobj in enumerate(qobjs):
            job = backend.run(qobj=qobj, job_name="{}_{}".format(name_prefix, i))
            end_index = start_index + len(qobj.experiments) - 1
            setattr(job, 'start_index', start_index)
            setattr(job, 'end_index', end_index)
            start_index = end_index + 1
            jobs.append(job)
    except Exception as err:  # pylint: disable=broad-except
        job_error = IBMQJobManagerSubmitError(
            "Unable to submit job {} for experiments {}-{}.".format(i, start_index, end_index))
        job_error.__cause__ = err
        jobs.append(job_error)

    return jobs
