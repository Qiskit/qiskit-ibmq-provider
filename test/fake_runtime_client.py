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

"""Fake RuntimeClient."""

import time
import uuid
from concurrent.futures import ThreadPoolExecutor

from qiskit.providers.ibmq.credentials import Credentials
from qiskit.providers.ibmq.api.exceptions import RequestsApiError


class BaseFakeProgram:
    """Base class for faking a program."""

    def __init__(self, program_id, name, data, cost=600):
        """Initialize a fake program."""
        self._id = program_id
        self._name = name
        self._data = data
        self._cost = cost

    def to_dict(self, include_data=False):
        """Convert this program to a dictionary format."""
        out = {'id': self._id,
               'name': self._name,
               'cost': self._cost}
        if include_data:
            out['data'] = self._data
        return out


class BaseFakeRuntimeJob:
    """Base class for faking a runtime job."""

    _job_progress = [
        "PENDING",
        "RUNNING",
        "SUCCEEDED"
    ]

    _executor = ThreadPoolExecutor()

    def __init__(self, job_id, program_id, hub, group, project, backend_name, params):
        """Initialize a fake job."""
        self._job_id = job_id
        self._status = "PENDING"
        self._program_id = program_id
        self._hub = hub
        self._group = group
        self._project = project
        self._backend_name = backend_name
        self._params = params
        self._future = self._executor.submit(self._auto_progress)
        self._result = None

    def _auto_progress(self):
        """Automatically update job status."""
        for status in self._job_progress:
            time.sleep(0.5)
            self._status = status

        if self._status == "SUCCEEDED":
            self._result = "foo"

    def to_dict(self):
        """Convert to dictionary format."""
        return {'id': self._job_id,
                'hub': self._hub,
                'group': self._group,
                'project': self._project,
                'backend': self._backend_name,
                'status': self._status,
                'params': [self._params]}


class BaseFakeRuntimeClient:
    """Base class for faking the runtime client."""

    def __init__(self):
        """Initialize a fake runtime client."""
        self._programs = {}
        self._jobs = {}

    def list_programs(self):
        """List all progrmas."""
        programs = []
        for prog in self._programs.values():
            programs.append(prog.to_dict())
        return programs

    def program_create(self, program_name, program_data):
        """Create a program."""
        if isinstance(program_data, str):
            with open(program_data, 'rb') as file:
                program_data = file.read()
        program_id = uuid.uuid4().hex
        self._programs[program_id] = BaseFakeProgram(program_id, program_name, program_data)
        return {'id': program_id}

    def program_get(self, program_id: str):
        """Return a specific program."""
        return self._programs[program_id].to_dict()

    def program_get_data(self, program_id: str):
        """Return a specific program and its data."""
        return self._programs[program_id].to_dict(iclude_data=True)

    def program_run(
            self,
            program_id: str,
            credentials: Credentials,
            backend_name: str,
            params: str
    ):
        """Run the specified program."""
        job_id = uuid.uuid4().hex
        job = BaseFakeRuntimeJob(job_id=job_id, program_id=program_id,
                                 hub=credentials.hub, group=credentials.group,
                                 project=credentials.project, backend_name=backend_name,
                                 params=params)
        self._jobs[job_id] = job
        return {'id': job_id}

    def program_delete(self, program_id: str) -> None:
        """Delete the specified program."""
        if program_id not in self._programs:
            raise RequestsApiError("Program not found")
        del self._programs[program_id]

    def program_job_get(self, job_id):
        """Get the specific job."""
        if job_id not in self._jobs:
            raise RequestsApiError("Job not found")
        return self._jobs[job_id].to_dict()

    def program_job_results(self, job_id: str):
        """Get the results of a program job."""
        pass
