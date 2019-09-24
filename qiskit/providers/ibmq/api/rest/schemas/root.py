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

"""Schemas for root."""

from marshmallow.validate import OneOf
from qiskit.providers import JobStatus
from qiskit.providers.models.backendconfiguration import BackendConfigurationSchema
from qiskit.providers.ibmq.apiconstants import ApiJobKind
from qiskit.validation import BaseSchema
from qiskit.validation.fields import String, Dict, Nested, Boolean, List, Number


# Helper schemas.

class ProjectResponseSchema(BaseSchema):
    """Nested schema for ProjectsResponseSchema"""

    # Required properties.
    isDefault = Boolean(required=True)


class ProjectsResponseSchema(BaseSchema):
    """Nested schema for GroupResponseSchema"""

    # Required properties.
    project_name = String(required=True)
    project = Nested(ProjectResponseSchema, required=True)


class GroupResponseSchema(BaseSchema):
    """Nested schema for GroupsResponseSchema"""

    # Required properties.
    projects = Dict(Nested(ProjectsResponseSchema), required=True)


class GroupsResponseSchema(BaseSchema):
    """Nested schema for HubsResponseSchema"""

    # Required properties.
    group_name = String(required=True)
    group = Nested(GroupResponseSchema, required=True)


class CircuitErrorResponseSchema(BaseSchema):
    """Nested schema for CircuitResponseSchema"""

    # Required properties
    code = String(required=True, validate=OneOf(['GENERIC_ERROR', 'HUB_NOT_FOUND']))


class BackendRequestSchema(BaseSchema):
    """Nested schema for JobsRequestSchema"""

    # Required properties
    name = String(required=True, description="the name of the backend.")


class JobsStatusFilterQueryParamRequestSchema(BaseSchema):
    """Nested schema for JobsStatusRequestSchema"""

    # Optional properties
    where = Dict(attribute="extra_filter", required=False,
                 description="additional filtering passed to the query.")

    # Required properties
    order = String(required=True, default="creationDate DESC")
    limit = Number(required=True, description="maximum number of items to return.")
    skip = Number(required=True, description="offset for the items to return.")


# Endpoint schemas.

class HubsResponseSchema(BaseSchema):
    """Schema for HubsResponse"""
    pass

    # pylint: disable=pointless-string-statement
    """ Commented out until https://github.com/Qiskit/qiskit-terra/issues/3021 is addressed
    # Required properties.
    name = String(required=True)
    groups = Dict(Nested(GroupsResponseSchema), required=True)
    """


class CircuitRequestSchema(BaseSchema):
    """Schema for CircuitRequest"""

    # Required properties
    name = String(required=True, description="name of the Circuit.")
    params = Dict(required=True, description="arguments for the Circuit.")


class CircuitResponseSchema(BaseSchema):
    """Schema for CircuitResponse"""
    # pylint: disable=invalid-name

    # Optional properties
    error = Dict(Nested(CircuitErrorResponseSchema), required=False)

    # Required properties
    id = String(required=True, description="the job ID of an already submitted job.")
    creationDate = String(required=True, description="when the job was run.")
    status = String(required=True, description="`status` field directly from the API response.")


class BackendsResponseSchema(BaseSchema):
    """Schema for BackendResponse"""

    # Required properties
    backends = List(Nested(BackendConfigurationSchema, required=True))


class JobsRequestSchema(BaseSchema):
    """Schema for JobsRequest"""

    # Optional properties
    name = String(required=False, description="custom name to be assigned to the job.")

    # Required properties
    qObject = Dict(required=True, description="the Qobj to be executed, as a dictionary.")
    backend = Nested(BackendRequestSchema, required=True)
    shots = Number(required=True)


class JobsResponseSchema(BaseSchema):
    """Schema for JobsResponse"""
    # pylint: disable=invalid-name

    # Optional properties
    error = String(required=False)

    # Required properties
    id = String(required=True)
    status = String(required=True, validate=OneOf([status.value for status in JobStatus]))
    creationDate = String(required=True)


class JobsStatusRequestSchema(BaseSchema):
    """Schema for JobsStatusRequest"""

    # Required properties
    filter = Nested(JobsStatusFilterQueryParamRequestSchema, required=True)


class JobsStatusResponseSchema(BaseSchema):
    """Schema for JobsStatusResponse"""
    # pylint: disable=invalid-name

    # Required properties
    id = String(required=True, description="the job ID of an already submitted job.")
    kind = String(required=True, validate=OneOf([kind.name for kind in ApiJobKind]))
    creationDate = String(required=True, description="when the job was run.")
    status = String(required=True)
