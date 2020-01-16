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

"""Fake AccountClient."""

# TODO This can probably be merged with the one in test_ibmq_job_states
import time
import copy
from random import randrange
import uuid
from concurrent.futures import ThreadPoolExecutor, wait

from qiskit.test.mock.backends.poughkeepsie.fake_poughkeepsie import FakePoughkeepsie
from qiskit.providers.ibmq.apiconstants import ApiJobStatus, API_JOB_FINAL_STATES
from qiskit.providers.ibmq.api.exceptions import RequestsApiError


VALID_RESULT_RESPONSE = {
    'backend_name': 'ibmqx2',
    'backend_version': '1.1.1',
    'job_id': 'XC1323XG2',
    'qobj_id': 'Experiment1',
    'success': True,
    'results': [
        {
            'header': {
                'name': 'Bell state',
                'memory_slots': 2,
                'creg_sizes': [['c', 2]],
                'clbit_labels': [['c', 0], ['c', 1]],
                'qubit_labels': [['q', 0], ['q', 1]]
            },
            'shots': 1024,
            'status': 'DONE',
            'success': True,
            'data': {
                'counts': {
                    '0x0': 484, '0x3': 540
                }
            }
        }
    ]
}


class BaseFakeJob:
    """Base class for faking a remote job."""

    _job_progress = [
        ApiJobStatus.CREATING,
        ApiJobStatus.VALIDATING,
        ApiJobStatus.RUNNING,
        ApiJobStatus.COMPLETED
    ]

    def __init__(self, executor, job_id, qobj, backend_name,
                 job_tags=None, share_level=None):
        """Initialize a fake job."""
        self.job_id = job_id
        self.status = ApiJobStatus.CREATING
        self.qobj = qobj
        self.future = executor.submit(self._auto_progress)
        self.result = None
        self.backend_name = backend_name
        self._share_level = share_level
        self._job_tags = job_tags

    def _auto_progress(self):
        """Automatically update job status."""
        for status in self._job_progress:
            time.sleep(0.5)
            self.status = status

        if self.status == ApiJobStatus.COMPLETED:
            new_result = copy.deepcopy(VALID_RESULT_RESPONSE)
            new_result['results'][0]['data']['counts'] = {
                '0x0': randrange(1024), '0x3': randrange(1024)}
            self.result = new_result

    def data(self):
        """Return job data."""
        data = {
            'id': self.job_id,
            'kind': 'q-object',
            'status': self.status.value,
            'creationDate': '2019-01-01T13:15:58.425972',
            'backend': {'name': self.backend_name}
        }
        if self._share_level:
            data['share_level'] = self._share_level
        if self._job_tags:
            data['tags'] = self._job_tags

        return data

    def cancel(self):
        """Cancel the job."""
        self.future.cancel()
        wait([self.future])
        self.status = ApiJobStatus.CANCELLED
        self.result = None


class CancelableFakeJob(BaseFakeJob):
    """Fake job that can be canceled."""

    _job_progress = [
        ApiJobStatus.CREATING,
        ApiJobStatus.VALIDATING,
        ApiJobStatus.RUNNING
    ]


class BaseFakeAccountClient:
    """Base class for faking the AccountClient."""

    def __init__(self, job_limit=-1, job_class=BaseFakeJob):
        """Initialize a fake account client."""
        self._jobs = {}
        self._result_retrieved = []
        self._job_limit = job_limit
        self._executor = ThreadPoolExecutor()
        self._job_class = job_class

    def list_jobs_statuses(self, limit, skip, *_args, **_kwargs):
        """Return a list of statuses of jobs."""
        job_data = []
        for job in self._jobs[skip:skip+limit]:
            job_data.append(job.data())
        return job_data

    def job_submit(self, backend_name, qobj_dict, job_share_level, job_tags, *_args, **_kwargs):
        """Submit a Qobj to a device."""
        if self._job_limit != -1 and self._running_jobs() >= self._job_limit:
            raise RequestsApiError(
                '400 Client Error: Bad Request for url: <url>.  User reached '
                'the maximum limits of concurrent jobs, Error code: 3458.')

        new_job_id = uuid.uuid4().hex
        new_job = self._job_class(executor=self._executor, job_id=new_job_id,
                                  qobj=qobj_dict, backend_name=backend_name,
                                  share_level=job_share_level.value, job_tags=job_tags)
        self._jobs[new_job_id] = new_job
        return new_job.data()

    def job_download_qobj(self, job_id, *_args, **_kwargs):
        """Retrieve and return a Qobj."""
        return self._jobs[job_id].qobj

    def job_result(self, job_id, *_args, **_kwargs):
        """Return a random job result."""
        if job_id in self._result_retrieved:
            raise ValueError("Result already retrieved for job {}!".format(job_id))
        self._result_retrieved.append(job_id)
        return self._jobs[job_id].result

    def job_get(self, job_id, *_args, **_kwargs):
        """Return information about a job."""
        return self._jobs[job_id].data()

    def job_status(self, job_id, *_args, **_kwargs):
        """Return the status of a job."""
        if job_id not in self._jobs:
            raise RequestsApiError('Job not found., Error code: 3250.')

        return {'status': self._jobs[job_id].status.value}

    def job_final_status(self, job_id, *_args, **_kwargs):
        """Wait until the job progress to a final state."""
        status = self._jobs[job_id].status
        while status not in API_JOB_FINAL_STATES:
            time.sleep(0.5)
            status = self._jobs[job_id].status
        return self.job_status(job_id)

    def job_properties(self, *_args, **_kwargs):
        """Return the backend properties of a job."""
        return FakePoughkeepsie().properties()

    def job_cancel(self, job_id, *_args, **_kwargs):
        """Submit a request for cancelling a job."""
        self._jobs[job_id].cancel()
        return {'cancelled': True}

    def backend_job_limit(self, *_args, **_kwargs):
        """Return the job limit for the backend."""
        return {'maximumJobs': self._job_limit, 'runningJobs': self._running_jobs}

    def _running_jobs(self):
        running_jobs = 0
        for job in self._jobs.values():
            if job.status is ApiJobStatus.RUNNING:
                running_jobs += 1
        return running_jobs


class JobSubmitFailClient(BaseFakeAccountClient):
    """Fake AccountClient used to fail a job submit."""

    def job_submit(self, *_args, **_kwargs):  # pylint: disable=arguments-differ
        """Failing job submit."""
        raise RequestsApiError("Job submit failed!")
