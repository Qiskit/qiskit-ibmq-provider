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
from datetime import timedelta, datetime
import warnings

from qiskit.test.mock.backends.poughkeepsie.fake_poughkeepsie import FakePoughkeepsie
from qiskit.providers.ibmq.apiconstants import ApiJobStatus, API_JOB_FINAL_STATES, ApiJobShareLevel
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

API_STATUS_TO_INT = {
    ApiJobStatus.CREATING: 0,
    ApiJobStatus.VALIDATING: 1,
    ApiJobStatus.QUEUED: 2,
    ApiJobStatus.RUNNING: 3,
    ApiJobStatus.COMPLETED: 4,
    ApiJobStatus.ERROR_RUNNING_JOB: 4,
    ApiJobStatus.ERROR_VALIDATING_JOB: 4,
    ApiJobStatus.CANCELLED: 4
}


class BaseFakeJob:
    """Base class for faking a remote job."""

    _job_progress = [
        ApiJobStatus.CREATING,
        ApiJobStatus.VALIDATING,
        ApiJobStatus.QUEUED,
        ApiJobStatus.RUNNING,
        ApiJobStatus.COMPLETED
    ]

    def __init__(self, executor, job_id, qobj, backend_name, job_tags=None,
                 share_level=None, job_name=None, experiment_id=None,
                 run_mode=None, progress_time=0.5, **kwargs):
        """Initialize a fake job."""
        self._job_id = job_id
        self._status = ApiJobStatus.CREATING
        self.qobj = qobj
        self._result = None
        self._backend_name = backend_name
        self._share_level = share_level
        self._job_tags = job_tags
        self._job_name = job_name
        self._experiment_id = experiment_id
        self._creation_date = datetime.now()
        self._run_mode = run_mode
        self._queue_pos = kwargs.pop('queue_pos', 'auto')
        self._comp_time = kwargs.pop('est_completion', 'auto')
        self._queue_info = None
        self._progress_time = progress_time
        self._future = executor.submit(self._auto_progress)

    def _auto_progress(self):
        """Automatically update job status."""
        for status in self._job_progress:
            time.sleep(self._progress_time)
            self._status = status

        if self._status == ApiJobStatus.COMPLETED:
            self._save_result()
        elif self._status == ApiJobStatus.ERROR_RUNNING_JOB:
            self._save_bad_result()

    def _save_result(self):
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

    def _save_bad_result(self):
        new_result = copy.deepcopy(VALID_RESULT_RESPONSE)
        new_result['job_id'] = self._job_id
        new_result['backend_name'] = self._backend_name
        new_result['success'] = False
        new_result['error'] = {'message': 'Kaboom', 'code': 1234}
        self._result = new_result

    def data(self):
        """Return job data."""
        status = self._status
        data = {
            'job_id': self._job_id,
            'kind': 'q-object',
            'status': status.value,
            'creation_date': self._creation_date.isoformat(),
            '_backend_info': {'name': self._backend_name},
            'client_info': {'qiskit': '0.23.5'}
        }
        if self._share_level:
            data['share_level'] = self._share_level
        if self._job_tags:
            data['tags'] = self._job_tags.copy()
        if self._job_name:
            data['name'] = self._job_name
        if self._experiment_id:
            data['experiment_id'] = self._experiment_id
        if status == ApiJobStatus.ERROR_VALIDATING_JOB:
            data['error'] = {'message': 'Validation failed.', 'code': 1234}
        if status in [ApiJobStatus.RUNNING] + list(API_JOB_FINAL_STATES) and self._run_mode:
            data['run_mode'] = self._run_mode

        time_per_step = {}
        timestamp = self._creation_date
        for api_stat in API_STATUS_TO_INT:
            if API_STATUS_TO_INT[status] > API_STATUS_TO_INT[api_stat]:
                time_per_step[api_stat.value] = timestamp.isoformat()
                timestamp += timedelta(seconds=30)
            elif status == api_stat:
                time_per_step[api_stat.value] = timestamp.isoformat()
                timestamp += timedelta(seconds=30)
        data['time_per_step'] = time_per_step

        return data

    def _get_info_queue(self):
        self._queue_info = {
            'status': 'PENDING_IN_QUEUE',
            'position': randrange(1, 10) if self._queue_pos == 'auto' else self._queue_pos
        }
        if self._queue_info['position'] is None:
            return self._queue_info

        est_comp_ts = self._creation_date + timedelta(minutes=10*self._queue_info['position']) \
            if self._comp_time == 'auto' else self._comp_time
        if est_comp_ts is None:
            return self._queue_info

        self._queue_info['estimated_complete_time'] = est_comp_ts.isoformat()
        self._queue_info['estimated_start_time'] = \
            (est_comp_ts - timedelta(minutes=20)).isoformat()

        return self._queue_info

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

    def status_data(self):
        """Return job status data, including queue info."""
        status = self._status
        data = {'status': status.value}
        if status == ApiJobStatus.QUEUED:
            data['info_queue'] = self._get_info_queue()
            print(f">>>>> fake account client: job {self._job_id} queue info: {data['info_queue']}")
        return data

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
        ApiJobStatus.VALIDATING
    ]

    def __init__(self, *args, **kwargs):
        # failure_type can be "validation", "result", or "partial"
        self._failure_type = kwargs.pop('failure_type', 'validation')
        self._job_progress = FailedFakeJob._job_progress.copy()
        if self._failure_type == 'validation':
            self._job_progress.append(ApiJobStatus.ERROR_VALIDATING_JOB)
        else:
            self._job_progress.extend([ApiJobStatus.RUNNING, ApiJobStatus.ERROR_RUNNING_JOB])
        super().__init__(*args, **kwargs)

    def _save_bad_result(self):
        if self._failure_type != 'partial':
            return super()._save_bad_result()
        new_result = copy.deepcopy(VALID_RESULT_RESPONSE)
        new_result['job_id'] = self._job_id
        new_result['backend_name'] = self._backend_name
        new_result['success'] = False
        # Good first result.
        valid_result = copy.deepcopy(VALID_RESULT)
        counts = randrange(1024)
        valid_result['data']['counts'] = {
            '0x0': counts, '0x3': 1024-counts}
        new_result['results'].append(valid_result)

        for _ in range(1, len(self.qobj['experiments'])):
            valid_result = copy.deepcopy(VALID_RESULT)
            valid_result['success'] = False
            valid_result['status'] = 'This circuit failed.'
            new_result['results'].append(valid_result)
        self._result = new_result


class FixedStatusFakeJob(BaseFakeJob):
    """Fake job that stays in a specific status."""

    def __init__(self, *args, **kwargs):
        self._fixed_status = kwargs.pop('fixed_status')
        super().__init__(*args, **kwargs)

    def _auto_progress(self):
        """Automatically update job status."""
        for status in self._job_progress:
            time.sleep(0.5)
            self._status = status
            if status == self._fixed_status:
                break

        if self._status == ApiJobStatus.COMPLETED:
            self._save_result()


class BaseFakeAccountClient:
    """Base class for faking the AccountClient."""

    def __init__(self, job_limit=-1, job_class=BaseFakeJob, job_kwargs=None,
                 props_count=None, queue_positions=None, est_completion=None,
                 run_mode=None):
        """Initialize a fake account client."""
        self._jobs = {}
        self._results_retrieved = set()
        self._job_limit = job_limit
        self._executor = ThreadPoolExecutor()
        self._job_class = job_class
        if isinstance(self._job_class, list):
            self._job_class.reverse()
        self._job_kwargs = job_kwargs or {}
        self._props_count = props_count or 0
        self._props_date = datetime.now().isoformat()
        self._queue_positions = queue_positions.copy() if queue_positions else []
        self._queue_positions.reverse()
        self._est_completion = est_completion.copy() if est_completion else []
        self._est_completion.reverse()
        self._run_mode = run_mode

    def list_jobs_statuses(self, limit, skip, descending=True, extra_filter=None):
        """Return a list of statuses of jobs."""
        # pylint: disable=unused-argument
        print(f">>>>>>>> BaseFakeAccountClient.list_jobs_statuse extra_filter={extra_filter}")
        extra_filter = extra_filter or {}
        if all(fil in extra_filter for fil in ['creationDate', 'id']):
            return {}
        tag = extra_filter.get('tags', None)
        all_job_data = []
        for job in list(self._jobs.values())[skip:skip+limit]:
            job_data = job.data()
            print(f">>>>>>>> BaseFakeAccountClient.list_jobs_statuse tag is {tag}, in data {tag in job_data['tags']}")
            if tag is None or tag in job_data['tags']:
                all_job_data.append(job_data)
        if not descending:
            all_job_data.reverse()
        return all_job_data

    def job_submit(self, backend_name, qobj_dict, job_name, job_share_level,
                   job_tags, experiment_id, *_args, **_kwargs):
        """Submit a Qobj to a device."""
        if self._job_limit != -1 and self._unfinished_jobs() >= self._job_limit:
            raise RequestsApiError(
                '400 Client Error: Bad Request for url: <url>.  Reached '
                'maximum number of concurrent jobs, Error code: 3458.')

        new_job_id = uuid.uuid4().hex
        job_share_level = job_share_level or ApiJobShareLevel.NONE
        job_class = self._job_class.pop() \
            if isinstance(self._job_class, list) else self._job_class
        job_kwargs = copy.copy(self._job_kwargs)
        if self._queue_positions:
            job_kwargs['queue_pos'] = self._queue_positions.pop()
        if self._est_completion:
            job_kwargs['est_completion'] = self._est_completion.pop()

        run_mode = self._run_mode
        if run_mode == 'dedicated_once':
            run_mode = 'dedicated'
            self._run_mode = 'fairshare'

        new_job = job_class(
            executor=self._executor,
            job_id=new_job_id,
            qobj=qobj_dict,
            backend_name=backend_name,
            share_level=job_share_level.value,
            job_tags=job_tags,
            job_name=job_name,
            experiment_id=experiment_id,
            run_mode=run_mode,
            **job_kwargs)
        self._jobs[new_job_id] = new_job
        return new_job.data()

    def job_download_qobj(self, job_id, *_args, **_kwargs):
        """Retrieve and return a Qobj."""
        return copy.deepcopy(self._get_job(job_id).qobj)

    def job_result(self, job_id, *_args, **_kwargs):
        """Return a random job result."""
        if job_id in self._results_retrieved:
            warnings.warn(f'Result already retrieved for job {job_id}')
        self._results_retrieved.add(job_id)
        return self._get_job(job_id).result()

    def job_get(self, job_id, *_args, **_kwargs):
        """Return information about a job."""
        return self._get_job(job_id).data()

    def job_status(self, job_id, *_args, **_kwargs):
        """Return the status of a job."""
        return self._get_job(job_id).status_data()

    def job_final_status(self, job_id, *_args, **_kwargs):
        """Wait until the job progress to a final state."""
        job = self._get_job(job_id)
        status = job.status()
        while status not in API_JOB_FINAL_STATES:
            time.sleep(0.5)
            status_data = job.status_data()
            status = ApiJobStatus(status_data['status'])
            if _kwargs.get('status_queue', None):

                # data = {'status': status.value}
                # if status is ApiJobStatus.QUEUED:
                #     data['infoQueue'] = {'status': 'PENDING_IN_QUEUE',
                #                          'position': 1}
                _kwargs['status_queue'].put(status_data)
        return self.job_status(job_id)

    def job_properties(self, *_args, **_kwargs):
        """Return the backend properties of a job."""
        props = FakePoughkeepsie().properties().to_dict()
        if self._props_count > 0:
            self._props_count -= 1
            new_dt = datetime.now() + timedelta(hours=randrange(300))
            self._props_date = new_dt.isoformat()
        props['last_update_date'] = self._props_date
        return props

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

    def __init__(self, failed_indexes):
        """JobSubmitFailClient constructor."""
        self._failed_indexes = list(failed_indexes)
        self._job_count = -1
        super().__init__()

    def job_submit(self, *_args, **_kwargs):  # pylint: disable=arguments-differ
        """Failing job submit."""
        self._job_count += 1
        if self._job_count in self._failed_indexes:
            raise RequestsApiError('Job submit failed!')
        return super().job_submit(*_args, **_kwargs)


class JobTimeoutClient(BaseFakeAccountClient):
    """Fake AccountClient used to timeout waiting for job."""

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
