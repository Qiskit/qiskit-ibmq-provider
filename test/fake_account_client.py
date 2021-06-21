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
from qiskit.providers.ibmq.api.exceptions import RequestsApiError, UserTimeoutExceededError


VALID_RESULT_RESPONSE = {
    'backend_name': 'ibmqx2',
    'backend_version': '1.1.1',
    'job_id': 'XC1323XG2',
    'qobj_id': 'Experiment1',
    'success': True,
    'results': []
}
"""A valid job result response."""

VALID_RESULT = {
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


class BaseFakeJob:
    """Base class for faking a remote job."""

    _job_progress = [
        ApiJobStatus.CREATING,
        ApiJobStatus.VALIDATING,
        ApiJobStatus.RUNNING,
        ApiJobStatus.COMPLETED
    ]

    def __init__(self, executor, job_id, qobj, backend_name, job_tags=None,
                 job_name=None):
        """Initialize a fake job."""
        self._job_id = job_id
        self._status = ApiJobStatus.CREATING
        self.qobj = qobj
        self._future = executor.submit(self._auto_progress)
        self._result = None
        self._backend_name = backend_name
        self._job_tags = job_tags
        self._job_name = job_name

    def _auto_progress(self):
        """Automatically update job status."""
        for status in self._job_progress:
            time.sleep(0.5)
            self._status = status

        if self._status == ApiJobStatus.COMPLETED:
            new_result = copy.deepcopy(VALID_RESULT_RESPONSE)
            for _ in range(len(self.qobj['experiments'])):
                valid_result = copy.deepcopy(VALID_RESULT)
                counts = randrange(1024)
                valid_result['data']['counts'] = {
                    '0x0': counts, '0x3': 1024-counts}
                new_result['results'].append(valid_result)
            new_result['job_id'] = self._job_id
            new_result['backend_name'] = self._backend_name
            self._result = new_result

    def data(self):
        """Return job data."""
        data = {
            'job_id': self._job_id,
            'kind': 'q-object',
            'status': self._status.value,
            'creation_date': '2019-01-01T13:15:58.425972',
            '_backend_info': {'name': self._backend_name}
        }
        if self._job_tags:
            data['tags'] = self._job_tags.copy()
        if self._job_name:
            data['name'] = self._job_name

        return data

    def cancel(self):
        """Cancel the job."""
        self._future.cancel()
        wait([self._future])
        self._status = ApiJobStatus.CANCELLED
        self._result = None

    def result(self):
        """Return job result."""
        if not self._result:
            raise RequestsApiError('Result is not available')
        return self._result

    def status(self):
        """Return job status."""
        return self._status

    def name(self):
        """Return job name."""
        return self._job_name


class CancelableFakeJob(BaseFakeJob):
    """Fake job that can be canceled."""

    _job_progress = [
        ApiJobStatus.CREATING,
        ApiJobStatus.VALIDATING,
        ApiJobStatus.RUNNING
    ]


class NewFieldFakeJob(BaseFakeJob):
    """Fake job that contains additional fields."""

    def data(self):
        """Return job data."""
        data = super().data()
        data['new_field'] = 'foo'
        return data


class MissingFieldFakeJob(BaseFakeJob):
    """Fake job that does not contain required fields."""

    def data(self):
        """Return job data."""
        data = super().data()
        del data['job_id']
        return data


class FailedFakeJob(BaseFakeJob):
    """Fake job that fails."""

    _job_progress = [
        ApiJobStatus.CREATING,
        ApiJobStatus.VALIDATING,
        ApiJobStatus.RUNNING,
        ApiJobStatus.ERROR_RUNNING_JOB
    ]

    def data(self):
        """Return job data."""
        data = super().data()
        if self.status() == ApiJobStatus.ERROR_RUNNING_JOB:
            data['error'] = {'message': 'Job failed.', 'code': 1234}
        return data


class BaseFakeAccountClient:
    """Base class for faking the AccountClient."""

    def __init__(self, job_limit=-1, job_class=BaseFakeJob):
        """Initialize a fake account client."""
        self._jobs = {}
        self._results_retrieved = set()
        self._job_limit = job_limit
        self._executor = ThreadPoolExecutor()
        self._job_class = job_class
        if isinstance(self._job_class, list):
            self._job_class.reverse()

    def list_jobs_statuses(self, limit, skip, descending=True, extra_filter=None):
        """Return a list of statuses of jobs."""
        # pylint: disable=unused-argument
        job_data = []
        for job in list(self._jobs.values())[skip:skip+limit]:
            job_data.append(job.data())
        if not descending:
            job_data.reverse()
        return job_data

    def job_submit(self, backend_name, qobj_dict, job_name,
                   job_tags, *_args, **_kwargs):
        """Submit a Qobj to a device."""
        if self._job_limit != -1 and self._unfinished_jobs() >= self._job_limit:
            raise RequestsApiError(
                '400 Client Error: Bad Request for url: <url>.  Reached '
                'maximum number of concurrent jobs, Error code: 3458.')

        new_job_id = uuid.uuid4().hex
        job_class = self._job_class.pop() \
            if isinstance(self._job_class, list) else self._job_class
        new_job = job_class(
            executor=self._executor,
            job_id=new_job_id,
            qobj=qobj_dict,
            backend_name=backend_name,
            job_tags=job_tags,
            job_name=job_name)
        self._jobs[new_job_id] = new_job
        return new_job.data()

    def job_download_qobj(self, job_id, *_args, **_kwargs):
        """Retrieve and return a Qobj."""
        return copy.deepcopy(self._get_job(job_id).qobj)

    def job_result(self, job_id, *_args, **_kwargs):
        """Return a random job result."""
        if job_id in self._results_retrieved:
            raise ValueError('Result already retrieved for job {}!'.format(job_id))
        self._results_retrieved.add(job_id)
        return self._get_job(job_id).result()

    def job_get(self, job_id, *_args, **_kwargs):
        """Return information about a job."""
        return self._get_job(job_id).data()

    def job_status(self, job_id, *_args, **_kwargs):
        """Return the status of a job."""
        return {'status': self._get_job(job_id).status().value}

    def job_final_status(self, job_id, *_args, **_kwargs):
        """Wait until the job progress to a final state."""
        job = self._get_job(job_id)
        status = job.status()
        while status not in API_JOB_FINAL_STATES:
            time.sleep(0.5)
            status = job.status()
            if _kwargs.get('status_queue', None):
                data = {'status': status.value}
                if status is ApiJobStatus.QUEUED:
                    data['infoQueue'] = {'status': 'PENDING_IN_QUEUE',
                                         'position': 1}
                _kwargs['status_queue'].put(data)
        return self.job_status(job_id)

    def job_properties(self, *_args, **_kwargs):
        """Return the backend properties of a job."""
        return FakePoughkeepsie().properties()

    def job_cancel(self, job_id, *_args, **_kwargs):
        """Submit a request for cancelling a job."""
        self._get_job(job_id).cancel()
        return {'cancelled': True}

    def backend_job_limit(self, *_args, **_kwargs):
        """Return the job limit for the backend."""
        return {'maximumJobs': self._job_limit, 'runningJobs': self._unfinished_jobs()}

    def job_update_attribute(self, job_id, attr_name, attr_value, *_args, **_kwargs):
        """Update the specified job attribute with the given value."""
        job = self._get_job(job_id)
        if attr_name == 'name':
            job._job_name = attr_value
        if attr_name == 'tags':
            job._job_tags = attr_value.copy()
        return {attr_name: attr_value}

    def tear_down(self):
        """Clean up job threads."""
        for job_id in list(self._jobs.keys()):
            try:
                self._jobs[job_id].cancel()
            except KeyError:
                pass

    def _unfinished_jobs(self):
        """Return the number of unfinished jobs."""
        return sum(1 for job in self._jobs.values() if job.status() not in API_JOB_FINAL_STATES)

    def _get_job(self, job_id):
        """Return job if found."""
        if job_id not in self._jobs:
            raise RequestsApiError('Job not found. Error code: 3250.')
        return self._jobs[job_id]


class JobSubmitFailClient(BaseFakeAccountClient):
    """Fake AccountClient used to fail a job submit."""

    def __init__(self, max_fail_count=-1):
        """JobSubmitFailClient constructor."""
        self._fail_count = max_fail_count
        super().__init__()

    def job_submit(self, *_args, **_kwargs):  # pylint: disable=arguments-differ
        """Failing job submit."""
        if self._fail_count != 0:
            self._fail_count -= 1
            raise RequestsApiError('Job submit failed!')
        return super().job_submit(*_args, **_kwargs)


class JobTimeoutClient(BaseFakeAccountClient):
    """Fake AccountClient used to fail a job submit."""

    def __init__(self, *args, max_fail_count=-1, **kwargs):
        """JobTimeoutClient constructor."""
        self._fail_count = max_fail_count
        super().__init__(*args, **kwargs)

    def job_final_status(self, job_id, *_args, **_kwargs):
        """Wait until the job progress to a final state."""
        if self._fail_count != 0:
            self._fail_count -= 1
            raise UserTimeoutExceededError('Job timed out!')
        return super().job_final_status(job_id, *_args, **_kwargs)
