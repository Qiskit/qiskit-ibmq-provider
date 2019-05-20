# -*- coding: utf-8 -*-

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

"""Utilities for working with IBM Q Jobs."""

from datetime import datetime, timezone


def current_utc_time():
    """Gets the current time in UTC format.

    Returns:
        str: current time in UTC format.
    """
    datetime.utcnow().replace(tzinfo=timezone.utc).isoformat()


def is_job_queued(api_job_status_response):
    """Checks whether a job has been queued or not.

    Args:
        api_job_status_response (dict): status response of the job.

    Returns:
        Pair[boolean, int]: a pair indicating if the job is queued and in which
            position.
    """
    is_queued, position = False, 0
    if 'infoQueue' in api_job_status_response:
        if 'status' in api_job_status_response['infoQueue']:
            queue_status = api_job_status_response['infoQueue']['status']
            is_queued = queue_status == 'PENDING_IN_QUEUE'
        if 'position' in api_job_status_response['infoQueue']:
            position = api_job_status_response['infoQueue']['position']
    return is_queued, position


def build_error_report(results):
    """Build an user-friendly error report for a failed job.

    Args:
        results (dict): result section of the job response.

    Returns:
        str: the error report.
    """
    error_list = []
    for index, result in enumerate(results):
        if not result['success']:
            error_list.append('Experiment {}: {}'.format(index, result['status']))

    error_report = 'The following experiments failed:\n{}'.format('\n'.join(error_list))
    return error_report
