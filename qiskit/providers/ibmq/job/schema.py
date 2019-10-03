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

"""Schemas for job."""

from marshmallow import pre_load
from marshmallow.fields import Bool
from marshmallow.validate import Range

from qiskit.providers.ibmq.utils import to_python_identifier
from qiskit.validation import BaseSchema
from qiskit.validation.fields import Dict, String, Nested, Integer
from qiskit.qobj.qobj import QobjSchema
from qiskit.result.models import ResultSchema
from qiskit.providers.ibmq.apiconstants import ApiJobKind, ApiJobStatus

from ..utils.validators import EnumType


# Mapping between 'API job field': 'IBMQJob attribute', for solving name
# clashes.
FIELDS_MAP = {
    'id': 'job_id',
    'status': '_status',
    'backend': 'backend_info',
    'qObject': 'qobj',
    'qObjectResult': '_result'
}


# Helper schemas.

class JobResponseBackendSchema(BaseSchema):
    """Nested schema for JobResponseSchema"""

    # Required properties
    name = String(required=True)


# Endpoint schemas.

class JobResponseSchema(BaseSchema):
    """Schema for GET Jobs, GET Jobs/{id}, and POST Jobs responses."""
    # pylint: disable=invalid-name

    # Required properties.
    creation_date = String(required=True)
    id = String(required=True)
    kind = EnumType(required=True, enum_cls=ApiJobKind)
    status = EnumType(required=True, enum_cls=ApiJobStatus)

    # Optional properties
    allow_object_storage = Bool(required=False)
    backend = Nested(JobResponseBackendSchema, required=False)
    error = String(required=False)
    name = String(required=False)
    _result = Nested(ResultSchema, required=False)
    _qobj = Nested(QobjSchema, required=False)
    shots = Integer(required=False, validate=Range(min=0))
    time_per_step = Dict(required=False, keys=String, values=String)

    @pre_load
    def preprocess_field_names(self, data):
        """Pre-process the job response fields.

        Rename selected fields of the job response due to name clashes, and
        convert from camel-case the rest of the fields.

        TODO: when updating to terra 0.10, check if changes related to
        marshmallow 3 allow to use directly `data_key`, as in 0.9 terra
        duplicates the unknown keys.
        """
        rename_map = {}
        for field_name in data:
            if field_name in FIELDS_MAP:
                rename_map[field_name] = FIELDS_MAP[field_name]
            else:
                rename_map[field_name] = to_python_identifier(field_name)

        for old_name, new_name in rename_map.items():
            data[new_name] = data.pop(old_name)
