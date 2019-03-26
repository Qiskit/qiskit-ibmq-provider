# -*- coding: utf-8 -*-

# Copyright 2019, IBM.
#
# This source code is licensed under the Apache License, Version 2.0 found in
# the LICENSE.txt file in the root directory of this source tree.

"""Values used by the API for a job status."""

import enum


class ApiJobStatus(enum.Enum):
    """Possible values used by the API for a job status.

    The enum names represent the strings returned by the API verbatim in
    several endpoints (`status()`, websocket information, etc). The general
    flow is:

    `CREATING -> CREATED -> VALIDATING -> VALIDATED -> RUNNING -> COMPLETED`
    """

    CREATING = 'CREATING'
    CREATED = 'CREATED'
    VALIDATING = 'VALIDATING'
    VALIDATED = 'VALIDATED'
    RUNNING = 'RUNNING'
    COMPLETED = 'COMPLETED'

    CANCELLED = 'CANCELLED'
    ERROR_CREATING_JOB = 'ERROR_CREATING_JOB'
    ERROR_VALIDATING_JOB = 'ERROR_VALIDATING_JOB'
    ERROR_RUNNING_JOB = 'ERROR_RUNNING_JOB'


API_JOB_FINAL_STATES = (
    ApiJobStatus.COMPLETED,
    ApiJobStatus.CANCELLED,
    ApiJobStatus.ERROR_CREATING_JOB,
    ApiJobStatus.ERROR_VALIDATING_JOB,
    ApiJobStatus.ERROR_RUNNING_JOB
)
