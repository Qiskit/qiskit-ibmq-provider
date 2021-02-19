# This code is part of Qiskit.
#
# (C) Copyright IBM 2021.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""IBM Quantum Experience composite job."""

import re
import logging
from typing import Dict, Optional, Tuple, Any, List, Callable, Union, Set
import warnings
import uuid
from datetime import datetime
from concurrent import futures
import queue
from collections import defaultdict, OrderedDict
import threading
import copy
from functools import wraps
import time
import traceback

from qiskit.compiler import assemble
from qiskit.providers.jobstatus import JOB_FINAL_STATES, JobStatus
from qiskit.providers.models import BackendProperties
from qiskit.qobj import QasmQobj, PulseQobj
from qiskit.result import Result
from qiskit.providers.ibmq import ibmqbackend  # pylint: disable=unused-import
from qiskit.assembler.disassemble import disassemble
from qiskit.circuit.quantumcircuit import QuantumCircuit
from qiskit.pulse import Schedule
from qiskit.result.models import ExperimentResult

from ..apiconstants import API_JOB_FINAL_STATES
from ..api.clients import AccountClient
from ..utils.utils import validate_job_tags, api_status_to_job_status
from .exceptions import (IBMQJobApiError, IBMQJobFailureError, IBMQJobTimeoutError,
                         IBMQJobInvalidStateError)
from .queueinfo import QueueInfo
from .utils import auto_retry, JOB_STATUS_TO_INT, JobStatusQueueInfo, last_job_stat_pos
from .ibmqjob import IBMQJob
from .ibmq_circuit_job import IBMQCircuitJob
from ..exceptions import IBMQBackendJobLimitError


class SubJob:

    def __init__(
            self,
            start_index: int,
            end_index: int,
            job_index: int,
            total: int
    ) -> None:
        self.start_index = start_index
        self.end_index = end_index
        self.job_index = job_index
        self.total_jobs = total
        self.job = None
