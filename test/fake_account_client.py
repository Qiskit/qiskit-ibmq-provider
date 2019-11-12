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


VALID_JOB_RESPONSE = {
    'id': 'TEST_ID',
    'kind': 'q-object',
    'status': 'CREATING',
    'creationDate': '2019-01-01T13:15:58.425972'
}

VALID_STATUS_RESPONSE = {
    'status': 'COMPLETED'
}

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


class BaseFakeAccountClient:
    """Base class for faking the AccountClient."""

    def __init__(self):
        self._jobs = {}
        self._result_retrieved = []

    def list_jobs_statuses(self, *_args, **_kwargs):
        """Return a list of statuses of jobs."""
        raise NotImplementedError

    def job_submit(self, *_args, **_kwargs):
        """Submit a Qobj to a device."""
        new_job_id = str(time.time()).replace('.', '')
        while new_job_id in self._jobs:
            new_job_id += "_"
        response = copy.deepcopy(VALID_JOB_RESPONSE)
        response['id'] = new_job_id
        self._jobs[new_job_id] = response
        return response

    def job_download_qobj(self, *_args, **_kwargs):
        """Retrieve and return a Qobj."""
        raise NotImplementedError

    def job_result(self, job_id, *_args, **_kwargs):
        """Return a random job result."""
        if job_id in self._result_retrieved:
            raise ValueError("Result already retrieved for job {}!".format(job_id))
        self._result_retrieved.append(job_id)
        result = copy.deepcopy(VALID_RESULT_RESPONSE)
        result['results'][0]['data']['counts'] = {
            '0x0': randrange(1024), '0x3': randrange(1024)}
        return result

    def job_get(self, job_id, *_args, **_kwargs):
        """Return information about a job."""
        job = self._jobs[job_id]
        job['status'] = 'COMPLETED'
        return job

    def job_status(self, *_args, **_kwargs):
        """Return the status of a job."""
        return VALID_STATUS_RESPONSE

    def job_final_status(self, *_args, **_kwargs):
        """Wait until the job progress to a final state."""
        return VALID_STATUS_RESPONSE

    def job_properties(self, *_args, **_kwargs):
        """Return the backend properties of a job."""
        raise NotImplementedError

    def job_cancel(self, *_args, **_kwargs):
        """Submit a request for cancelling a job."""
        raise NotImplementedError
