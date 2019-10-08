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

"""Job specific for Circuits."""

from typing import Dict, Any

from qiskit.providers import JobError  # type: ignore[attr-defined]
from qiskit.providers.jobstatus import JOB_FINAL_STATES

from .ibmqjob import IBMQJob
from ..apiconstants import ApiJobStatus


class CircuitJob(IBMQJob):
    """Job specific for use with Circuits.

    Note: this class is experimental, and currently only supports the
    customizations needed for using it with the manager (which implies
    initializing with a job_id:

        * _wait_for_completion()
        * status()
        * result()

    In general, the changes involve using a different `self._api.foo()` method
    for adjusting to the Circuits particularities.
    """

    def status(self) -> str:
        if self._status in JOB_FINAL_STATES:
            return self._status

        try:
            # TODO: See result values
            api_response = self._api.circuit_job_status(self._job_id)
            self._update_status_position(ApiJobStatus(api_response['status']),
                                         api_response.get('infoQueue', None))
        # pylint: disable=broad-except
        except Exception as err:
            raise JobError(str(err))

        return self._status

    def _get_job(self) -> Dict[str, Any]:
        if self._cancelled:
            raise JobError(
                'Job result impossible to retrieve. The job was cancelled.')

        return self._api.circuit_job_get(self._job_id)
