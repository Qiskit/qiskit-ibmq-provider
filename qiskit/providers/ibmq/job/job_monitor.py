# This code is part of Qiskit.
#
# (C) Copyright IBM 2017, 2018.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.


"""A module for monitoring jobs."""

import sys
import time
from typing import TextIO, Optional

from .ibmqjob import IBMQJob
from ..utils.converters import duration_difference


def _text_checker(job: IBMQJob,
                  interval: float,
                  _interval_set: bool = False,
                  output: TextIO = sys.stdout) -> None:
    """A text-based job status checker.

    Args:
        job: The job to check.
        interval: The interval at which to check.
        _interval_set: Was interval time set by user?
        output: The file like object to write status messages to.
            By default this is sys.stdout.

    """
    status = job.status()
    msg = status.value
    prev_msg = msg
    msg_len = len(msg)
    prev_time_str = ''

    print('\r%s: %s' % ('Job Status', msg), end='', file=output)
    while status.name not in ['DONE', 'CANCELLED', 'ERROR']:
        time.sleep(interval)
        status = job.status()
        msg = status.value

        if status.name == 'QUEUED':
            queue_info = job.queue_info()

            if queue_info:
                if queue_info.estimated_start_time:
                    est_time = queue_info.estimated_start_time
                    time_str = duration_difference(est_time)
                    prev_time_str = time_str

            else:
                time_str = prev_time_str

            msg += ' ({queue}) [Est. wait time: {time}]'.format(queue=job.queue_position(),
                                                                time=time_str)

            if job.queue_position() is None:
                if not _interval_set:
                    interval = 2
            elif not _interval_set:
                interval = max(job.queue_position(), 2)
        else:
            if not _interval_set:
                interval = 2

        if status.name == 'RUNNING':
            msg = 'RUNNING'
            job_mode = job.scheduling_mode()
            if job_mode:
                msg += ' - {}'.format(job_mode)

        elif status.name == 'ERROR':
            msg = 'ERROR - {}'.format(job.error_message())

        # Adjust length of message so there are no artifacts
        if len(msg) < msg_len:
            msg += ' ' * (msg_len - len(msg))
        elif len(msg) > msg_len:
            msg_len = len(msg)

        if msg != prev_msg:
            print('\r%s: %s' % ('Job Status', msg), end='', file=output)
            prev_msg = msg

    print('', file=output)


def job_monitor(job: IBMQJob,
                interval: Optional[float] = None,
                output: TextIO = sys.stdout) -> None:
    """Monitor the status of an ``IBMQJob`` instance.

    Args:
        job: Job to monitor.
        interval: Time interval between status queries.
        output: The file like object to write status messages to.
            By default this is sys.stdout.
    """
    if interval is None:
        _interval_set = False
        interval = 5
    else:
        _interval_set = True

    _text_checker(job, interval, _interval_set,
                  output=output)
