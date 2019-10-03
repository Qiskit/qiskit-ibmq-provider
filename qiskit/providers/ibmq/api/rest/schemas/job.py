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
from marshmallow.fields import Bool
from marshmallow.validate import OneOf
from qiskit.providers.ibmq.apiconstants import ApiJobStatus, ApiJobKind
from qiskit.validation import BaseSchema
from qiskit.validation.fields import Dict, String, Url, Nested, Integer


# Helper schemas.

class FieldsFilterRequestSchema(BaseSchema):
    """Nested schema for SelfFilterQueryParamRequestSchema"""

    # Required properties
    fields = Dict(keys=String, values=Bool)


class InfoQueueResponseSchema(BaseSchema):
    """Nested schema for StatusResponseSchema"""

    # Optional properties
    position = Integer(required=False, missing=0)
    status = String(required=False)


class JobResponseSchema(BaseSchema):
    """Nested schema for CallbackUploadResponseSchema"""
    # pylint: disable=invalid-name

    # Optional properties
    error = String(required=False)

    # Required properties
    id = String(required=True)
    kind = String(required=True)
    creationDate = String(required=True, description="when the job was run")


# Endpoint schemas.

class SelfFilterQueryParamRequestSchema(BaseSchema):
    """Schema for SelfFilterQueryParamRequest"""

    # Required properties
    filter = Nested(FieldsFilterRequestSchema, required=True)


class SelfResponseSchema(BaseSchema):
    """Schema for SelfResponseSchema"""
    # pylint: disable=invalid-name

    # Optional properties
    error = String(required=False)

    id = String(required=True)
    kind = String(required=True, validate=OneOf([kind.value for kind in ApiJobKind]))
    status = String(required=True, validate=OneOf([status.value for status in ApiJobStatus]))
    creationDate = String(required=True, description="when the job was run")


class PropertiesResponseSchema(BaseSchema):
    """Schema for PropertiesResponse"""
    pass


class StatusResponseSchema(BaseSchema):
    """Schema for StatusResponse"""

    # Optional properties
    infoQueue = Nested(InfoQueueResponseSchema, required=False)

    # Required properties
    status = String(required=True, validate=OneOf([status.value for status in ApiJobStatus]))


class CancelResponseSchema(BaseSchema):
    """Schema for CancelResponse"""

    # Optional properties
    error = String(required=False)


class UploadUrlResponseSchema(BaseSchema):
    """Schema for UploadUrlResponse"""

    # Required properties
    url = Url(required=True, description="upload object storage URL.")


class DownloadUrlResponseSchema(BaseSchema):
    """Schema for DownloadUrlResponse"""

    # Required properties
    url = Url(required=True, description="download object storage URL.")


class ResultUrlResponseSchema(BaseSchema):
    """Schema for ResultUrlResponse"""

    # Required properties
    url = Url(required=True, description="object storage URL.")


class CallbackUploadResponseSchema(BaseSchema):
    """Schema for CallbackUploadResponse"""

    # Required properties
    job = Nested(JobResponseSchema, required=True)


class CallbackDownloadResponseSchema(BaseSchema):
    """Schema for CallbackDownloadResponse"""
    pass
