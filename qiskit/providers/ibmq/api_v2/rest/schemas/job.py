# -*- coding: utf-8 -*-

# This code is part of Qiskit.
#
# (C) Copyright IBM 2017, 2019.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Schemas for job."""
from marshmallow.validate import OneOf
from qiskit.providers.ibmq.apiconstants import ApiJobStatus
from qiskit.validation import BaseSchema
from qiskit.validation.fields import String, Url, Nested, Integer


# Helper schemas.

class InfoQueueResponseSchema(BaseSchema):
    """Nested schema for StatusResponseSchema"""

    # Optional properties
    position = Integer(required=False, missing=0)
    status = String(required=False, missing=False)


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
    upload_url = Url(required=True, description="upload object storage URL.")


class DownloadUrlResponseSchema(BaseSchema):
    """Schema for DownloadUrlResponse"""

    # Required properties
    download_url = Url(required=True, description="download object storage URL.")


class ResultUrlResponseSchema(BaseSchema):
    """Schema for ResultUrlResponse"""

    # Required properties
    download_url = Url(required=True, description="object storage URL.")


class CallbackUploadResponseSchema(BaseSchema):
    """Schema for CallbackUploadResponse"""

    # Required properties
    job = Nested(JobResponseSchema, required=True)


class CallbackDownloadResponseSchema(BaseSchema):
    """Schema for CallbackDownloadResponse"""
    pass
