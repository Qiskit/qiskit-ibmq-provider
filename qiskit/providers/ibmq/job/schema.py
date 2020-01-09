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

"""Schemas for job."""

from marshmallow import pre_load

from qiskit.validation import BaseSchema
from qiskit.validation.fields import Dict, String, Nested, Integer, Boolean, DateTime, List
from qiskit.qobj.qobj import QobjSchema
from qiskit.result.models import ResultSchema

from qiskit.providers.ibmq.utils.fields import Enum, map_field_names
from qiskit.providers.ibmq.apiconstants import ApiJobKind, ApiJobStatus


# Mapping between 'API job field': 'IBMQJob attribute', for solving name
# clashes.
FIELDS_MAP = {
    'id': '_job_id',
    'status': '_api_status',
    'backend': '_backend_info',
    'creationDate': '_creation_date',
    'qObject': '_qobj',
    'qObjectResult': '_result',
    'error': '_error',
    'name': '_name',
    'timePerStep': '_time_per_step',
    'shots': '_api_shots',
    'tags': '_tags'
}


# Helper schemas.

class JobResponseBackendSchema(BaseSchema):
    """Nested schema for the backend field in JobResponseSchema."""

    # Required properties
    name = String(required=True)


class JobResponseErrorSchema(BaseSchema):
    """Nested schema for the error field in JobResponseSchema."""

    # Required properties
    code = Integer(required=True)
    message = String(required=True)


# Endpoint schemas.

class JobResponseSchema(BaseSchema):
    """Schema for IBMQJob.

    Schema for an `IBMQJob`. The following conventions are in use in order to
    provide enough flexibility in regards to attributes:

    * the "Required properties" reflect attributes that will always be present
      in the model.
    * the "Optional properties with a default value" reflect attributes that
      are always present in the model, but might contain uninitialized values
      depending on the state of the job.
    * some properties are prepended by underscore due to name clashes and extra
      constraints in the IBMQJob class (for example, existing IBMQJob methods
      that have the same name as a response field).

    The schema is used for GET Jobs, GET Jobs/{id}, and POST Jobs responses.
    """
    # pylint: disable=invalid-name

    # Required properties.
    _creation_date = DateTime(required=True)
    _job_id = String(required=True)
    _api_status = Enum(required=True, enum_cls=ApiJobStatus)

    # Optional properties with a default value.
    kind = Enum(enum_cls=ApiJobKind, missing=None)
    _name = String(missing=None)
    _time_per_step = Dict(keys=String, values=String, missing=None)
    _result = Nested(ResultSchema, missing=None)
    _qobj = Nested(QobjSchema, missing=None)
    _error = Nested(JobResponseErrorSchema, missing=None)
    _tags = List(String, missing=[])

    # Optional properties
    _backend_info = Nested(JobResponseBackendSchema)
    allow_object_storage = Boolean()

    @pre_load
    def preprocess_field_names(self, data, **_):  # type: ignore
        """Pre-process the job response fields.

        Rename selected fields of the job response due to name clashes, and
        convert from camel-case the rest of the fields.

        TODO: when updating to terra 0.10, check if changes related to
        marshmallow 3 allow to use directly `data_key`, as in 0.9 terra
        duplicates the unknown keys.
        """
        return map_field_names(FIELDS_MAP, data)
