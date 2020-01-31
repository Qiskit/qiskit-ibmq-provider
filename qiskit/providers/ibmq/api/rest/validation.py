# -*- coding: utf-8 -*-

# This code is part of Qiskit.
#
# (C) Copyright IBM 2019, 2020.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Schemas for validation."""
# TODO The schemas defined here should be merged with others under rest/schemas
# when they are ready
from marshmallow import pre_load
from marshmallow.validate import OneOf

from qiskit.providers.ibmq.apiconstants import ApiJobStatus
from qiskit.validation import BaseSchema
from qiskit.validation.fields import String, Nested, Integer, DateTime, Float

from qiskit.providers.ibmq.utils.fields import map_field_names


# Helper schemas.

class InfoQueueResponseSchema(BaseSchema):
    """Queue information schema, nested in StatusResponseSchema"""

    # Optional properties
    position = Integer(required=False, missing=None)
    _status = String(required=False, missing=None)
    estimated_start_time = DateTime(required=False, missing=None)
    estimated_complete_time = DateTime(required=False, missing=None)
    hub_priority = Float(required=False, missing=None)
    group_priority = Float(required=False, missing=None)
    project_priority = Float(required=False, missing=None)

    @pre_load
    def preprocess_field_names(self, data, **_):  # type: ignore
        """Pre-process the info queue response fields."""
        FIELDS_MAP = {  # pylint: disable=invalid-name
            'status': '_status',
            'estimatedStartTime': 'estimated_start_time',
            'estimatedCompleteTime': 'estimated_complete_time',
            'hubPriority': 'hub_priority',
            'groupPriority': 'group_priority',
            'projectPriority': 'project_priority'
        }
        return map_field_names(FIELDS_MAP, data)


# Endpoint schemas.

class StatusResponseSchema(BaseSchema):
    """Schema for StatusResponse"""

    # Optional properties
    infoQueue = Nested(InfoQueueResponseSchema, required=False)

    # Required properties
    status = String(required=True, validate=OneOf([status.value for status in ApiJobStatus]))


class BackendJobLimitResponseSchema(BaseSchema):
    """Schema for BackendJobLimit"""

    # Optional properties
    maximum_jobs = Integer(required=True)
    running_jobs = Integer(required=True)

    @pre_load
    def preprocess_field_names(self, data, **_):  # type: ignore
        """Pre-process the jobs limit response fields."""
        FIELDS_MAP = {  # pylint: disable=invalid-name
            'maximumJobs': 'maximum_jobs',
            'runningJobs': 'running_jobs'
        }
        return map_field_names(FIELDS_MAP, data)
