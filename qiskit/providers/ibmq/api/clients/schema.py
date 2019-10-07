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

"""Schemas used by API clients."""

from qiskit.validation import BaseSchema
from qiskit.validation.fields import String, Nested, Integer
from qiskit.providers.ibmq.apiconstants import ApiJobStatus
from qiskit.providers.ibmq.utils.fields import Enum


# Helper schemas.

class InfoQueueResponseSchema(BaseSchema):
    """Nested schema for JobStatusResponseSchema"""

    # Optional properties
    position = Integer(required=False, missing=0)
    status = String(required=False)


# Endpoint schemas.

class JobStatusResponseSchema(BaseSchema):
    """Schema for JobStatusResponse."""
    status = Enum(required=True, enum_cls=ApiJobStatus)
    # Optional properties
    infoQueue = Nested(InfoQueueResponseSchema, required=False)
