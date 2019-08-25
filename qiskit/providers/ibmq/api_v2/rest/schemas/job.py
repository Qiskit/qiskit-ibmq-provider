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
from types import SimpleNamespace

from marshmallow import Schema, post_load, post_dump
from marshmallow.validate import OneOf
from marshmallow.exceptions import ValidationError

from qiskit.validation import BaseSchema
from qiskit.validation import BaseModel, bind_schema, ModelTypeValidator
from qiskit.validation.fields import String, Dict, DateTime
from qiskit.providers.jobstatus import JobStatus
from qiskit.providers.ibmq.apiconstants import ApiJobKind, ApiJobStatus


# class JobPostResponseSchema(BaseSchema):
#     id = String(required=True)
#     creationDate = String(required=True)


# class BaseSchema(Schema):
#     """Base class for Schemas for validated Qiskit classes.
#
#     Provides convenience functionality for the Qiskit common use case:
#
#     * deserialization into class instances instead of dicts.
#     * handling of unknown attributes not defined in the schema.
#
#     Attributes:
#          model_cls (type): class used to instantiate the instance. The
#          constructor is passed all named parameters from deserialization.
#     """
#
#     class Meta:
#         """In marshmallow3, all schemas are strict."""
#         # TODO: remove when upgrading to marshmallow3
#         strict = True
#
#     model_cls = SimpleNamespace
#
#     @post_load
#     def make_model(self, data):
#         """Make ``load`` return a ``model_cls`` instance instead of a dict."""
#         return self.model_cls(**data)


class BaseEnumType(ModelTypeValidator):

    def __init__(self, enum_cls, *args, **kwargs):
        self.valid_types = (str, enum_cls)
        self.valid_strs = [elem.value for elem in enum_cls]
        super().__init__(*args, **kwargs)

    def _serialize(self, value, attr, obj):
        # print(f">>>>>>> serialize, value={value}, attr={attr}, obj={obj}")
        return value.value

    def _deserialize(self, value, attr, data):
        # value is the data, attr is original field name, data is original dictionary
        # print(f">>>>>>> _deserialize, value={value}, attr={attr}, data={data}")
        return ApiJobKind(value)

    def check_type(self, value, attr, data):
        # Quick check of the type
        super().check_type(value, attr, data)

        if (isinstance(value, str)) and (value not in self.valid_strs):
            raise ValidationError("{} is {}, which is not an expected value.".format(attr, value))


class JobResponseSchema(BaseSchema):
    """Schema for GET /Jobs/{id} or POST /Jobs response."""
    # pylint: disable=invalid-name

    # Required properties.
    # _job_id = String(required=True, load_from='id', dump_to='id')
    id = String(required=True)
    kind = BaseEnumType(enum_cls=ApiJobKind, required=True)
    status = String(required=True, validate=OneOf([stat.value for stat in ApiJobStatus]))
    creationDate = String(required=True)


class JobErrorResponseSchema(BaseSchema):
    error = Dict(required=True)


@bind_schema(JobResponseSchema)
class JobModel(BaseModel):
    """Model for JobByIdModel.

    """

    def __init__(self, id, kind, status, creationDate, **kwargs):
        self._job_id = id
        self._job_kind = kind
        self.creation_date = creationDate
        self._api_status = status

        # Remove conflicting attributes
        kwargs.pop('backend', None)

        print(f">>>>>>>> JobModel.__init__, kwargs is {kwargs}")

        super().__init__(**kwargs)

# @bind_schema(JobPostResponseSchema)
# class JobPostModel(BaseModel):
#
#     def __init__(self, id, creationDate, **kwargs):
#         self.id = id
#         self.creation_date = creationDate
#
#         super().__init__(**kwargs)


@bind_schema(JobErrorResponseSchema)
class JobErrorModel(BaseModel):

    def __init__(self, error, **kwargs):
        self.error = error

        super().__init__(**kwargs)
