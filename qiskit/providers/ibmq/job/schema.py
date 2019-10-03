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

from marshmallow import post_load
from marshmallow.fields import Bool
from marshmallow.validate import Range

from qiskit.validation import BaseSchema
from qiskit.validation.fields import Dict, String, Nested, Integer
from qiskit.qobj.qobj import QobjSchema
from qiskit.result.models import ResultSchema
from qiskit.providers.ibmq.apiconstants import ApiJobKind, ApiJobStatus

from ..utils.validators import EnumType


class JobResponseBaseSchema(BaseSchema):
    """Base schema for job responses."""

    @post_load
    def make_model(self, data):
        """Overwrite parent method to return a dict instead of a model instance."""
        return data


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
    creationDate = String(required=True)
    id = String(required=True)
    kind = EnumType(required=True, enum_cls=ApiJobKind)
    status = EnumType(required=True, enum_cls=ApiJobStatus)

    # Optional properties
    allowObjectStorage = Bool(required=False)
    backend = Nested(JobResponseBackendSchema, required=False)
    error = String(required=False)
    name = String(required=False)
    qObjectResult = Nested(ResultSchema, required=False)
    qObject = Nested(QobjSchema, required=False)
    shots = Integer(required=False, validate=Range(min=0))
    timePerStep = Dict(required=False, keys=String, values=String)
