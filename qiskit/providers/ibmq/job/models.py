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

"""Models for job."""

from qiskit.providers.ibmq.api.rest.schemas.job import JobResponseSchema
from qiskit.providers.ibmq.utils import to_python_identifier
from qiskit.validation import BaseModel, bind_schema


@bind_schema(JobResponseSchema)
class JobModel(BaseModel):
    """Model for GetJobs, GetJobsById, and PostJobs."""

    def __init__(self, creationDate, id, kind, status, **kwargs):
        # pylint: disable=redefined-builtin
        # pylint: disable=invalid-name

        # Private attributes
        self._creation_date = creationDate
        self._job_id = id
        self._job_kind = kind
        self._api_job_status = status

        # Optional attributes. These are specifically defined to allow
        # auto-completion in an IDE.
        self.shots = kwargs.pop('shots', None)
        self.time_per_step = kwargs.pop('timePerStep', None)
        self._api_backend = kwargs.pop('backend', None)

        if not self.__dict__.get('name', None):
            self.name = kwargs.pop('name', None)

        if not self.__dict__.get('_qobj_dict', None):
            self._qobj_dict = kwargs.pop('qObject', None)

        # Additional attributes, converted to Python identifiers
        new_kwargs = {to_python_identifier(key): value for key, value in kwargs.items()}

        super().__init__(**new_kwargs)
