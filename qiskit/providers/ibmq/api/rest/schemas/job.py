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
from marshmallow.validate import OneOf, Range
from marshmallow.exceptions import ValidationError

from qiskit.validation import BaseSchema
from qiskit.validation import ModelTypeValidator
from qiskit.validation.fields import Dict, String, Url, Nested, Integer
from qiskit.qobj.qobj import QobjSchema
from qiskit.result.models import ResultSchema
from qiskit.providers.ibmq.apiconstants import ApiJobKind, ApiJobStatus


class JobResponseBaseSchema(BaseSchema):
    """Base schema for job responses."""

    @post_load
    def make_model(self, data):
        """Overwrite parent method to return a dict instead of a model instance."""
        return data


class EnumType(ModelTypeValidator):
    """Field for enums."""

    def __init__(self, enum_cls, *args, **kwargs):
        self.valid_types = (str, enum_cls)
        self.valid_strs = [elem.value for elem in enum_cls]
        self.enum_cls = enum_cls
        super().__init__(*args, **kwargs)

    def _serialize(self, value, attr, obj):
        return value.value

    def _deserialize(self, value, attr, data):
        # value is the data, attr is original field name, data is original dictionary
        self.check_type(value, attr, data)
        return self.enum_cls(value)

    def check_type(self, value, attr, data):
        # Quick check of the type
        super().check_type(value, attr, data)

        if (isinstance(value, str)) and (value not in self.valid_strs):
            raise ValidationError("{} is {}, which is not an expected value.".format(attr, value))


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


class JobResponseBackendSchema(BaseSchema):
    """Nested schema for JobResponseSchema"""

    # Required properties
    name = String(required=True)


# Endpoint schemas.

class JobResponseSchema(JobResponseBaseSchema):
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


class SelfFilterQueryParamRequestSchema(BaseSchema):
    """Schema for SelfFilterQueryParamRequest"""

    # Required properties
    filter = Nested(FieldsFilterRequestSchema, required=True)


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


class JobStatusResponseSchema(BaseSchema):
    """Schema for JobStatusResponse."""
    status = EnumType(required=True, enum_cls=ApiJobStatus)
    # Optional properties
    infoQueue = Nested(InfoQueueResponseSchema, required=False)
