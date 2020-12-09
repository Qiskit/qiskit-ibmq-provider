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

"""Values used by the API for different values."""

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
    TRANSPILING = 'TRANSPILING'
    TRANSPILED = 'TRANSPILED'
    VALIDATING = 'VALIDATING'
    VALIDATED = 'VALIDATED'
    RUNNING = 'RUNNING'
    COMPLETED = 'COMPLETED'
    PENDING_IN_QUEUE = 'PENDING_IN_QUEUE'
    QUEUED = 'QUEUED'
    CANCELLED = 'CANCELLED'
    ERROR_CREATING_JOB = 'ERROR_CREATING_JOB'
    ERROR_VALIDATING_JOB = 'ERROR_VALIDATING_JOB'
    ERROR_RUNNING_JOB = 'ERROR_RUNNING_JOB'
    ERROR_TRANSPILING_JOB = 'ERROR_TRANSPILING_JOB'


API_JOB_FINAL_STATES = (
    ApiJobStatus.COMPLETED,
    ApiJobStatus.CANCELLED,
    ApiJobStatus.ERROR_CREATING_JOB,
    ApiJobStatus.ERROR_VALIDATING_JOB,
    ApiJobStatus.ERROR_RUNNING_JOB,
    ApiJobStatus.ERROR_TRANSPILING_JOB
)


class ApiJobKind(enum.Enum):
    """Possible values used by the API for a job kind."""
    QOBJECT = 'q-object'
    QOBJECT_STORAGE = 'q-object-external-storage'
    CIRCUIT = 'q-circuit'


class ApiJobShareLevel(enum.Enum):
    """Possible values used by the API for job share levels."""
    GLOBAL = 'global'
    HUB = 'hub'
    GROUP = 'group'
    PROJECT = 'project'
    NONE = 'none'
