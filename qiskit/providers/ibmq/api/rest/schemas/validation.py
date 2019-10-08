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

"""Schemas for validation."""
# TODO The schemas defined here should be merged with others under rest/schemas
# when they are ready
from marshmallow.validate import OneOf
from qiskit.providers.ibmq.apiconstants import ApiJobStatus
from qiskit.validation import BaseSchema
from qiskit.validation.fields import String, Nested, Integer


# Helper schemas.

class InfoQueueResponseSchema(BaseSchema):
    """Nested schema for StatusResponseSchema"""

    # Optional properties
    position = Integer(required=False, missing=0)
    status = String(required=False)


# Endpoint schemas.

class StatusResponseSchema(BaseSchema):
    """Schema for StatusResponse"""

    # Optional properties
    infoQueue = Nested(InfoQueueResponseSchema, required=False)

    # Required properties
    status = String(required=True, validate=OneOf([status.value for status in ApiJobStatus]))
