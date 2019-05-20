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

"""Job specific for object storage Qobjs."""

from qiskit.providers import JobError
from qiskit.providers.jobstatus import JobStatus
from qiskit.result import Result

from .ibmqjob import IBMQJob
from ..api import ApiError


class IBMQStorageJob(IBMQJob):
    """IBM Q Job that uses object storage."""

    def _submit_callback(self):
        backend_name = self.backend().name()

        try:
            submit_info = self._api.job_submit_object_storage(
                self._qobj_payload, backend_name=backend_name)
        # pylint: disable=broad-except
        except Exception as err:
            # Undefined error during submission:
            # Capture and keep it for raising it when calling status().
            self._future_captured_exception = err
            return None

        # Error in the job after submission:
        # Transition to the `ERROR` final state.
        if 'error' in submit_info:
            self._status = JobStatus.ERROR
            self._api_error_msg = str(submit_info['error'])
            return submit_info

        # Submission success.
        self._creation_date = submit_info.get('creationDate')
        self._status = JobStatus.QUEUED
        self._job_id = submit_info.get('id')
        return submit_info

    def _wait_for_job(self, timeout=None, wait=5):
        self._wait_for_completion(timeout, wait)

        try:
            job_response = self._get_job()
            if not self._qobj_payload:
                self._qobj_payload = self._api.job_download_qobj_object_storage(
                    self._job_id)
        except ApiError as api_err:
            raise JobError(str(api_err))

        return job_response

    def result(self, timeout=None, wait=5):
        self._wait_for_completion(timeout=timeout, wait=wait)

        status = self.status()
        if status is not JobStatus.DONE:
            raise JobError('Invalid job state. The job should be DONE but '
                           'it is {}'.format(str(status)))

        if not self._result:
            # Retrieve the results via object storage.
            result_response = self._api.job_result_object_storage(self._job_id)
            self._result = Result.from_dict(result_response)

        return self._result
