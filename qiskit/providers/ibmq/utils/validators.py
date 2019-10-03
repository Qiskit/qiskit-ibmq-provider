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

"""Custom fields for validation."""

import enum
from typing import Dict, Union, Any
from marshmallow.exceptions import ValidationError

from qiskit.validation import ModelTypeValidator, BaseModel
from ..apiconstants import ApiJobKind, ApiJobStatus


class EnumType(ModelTypeValidator):
    """Field for enums."""

    def __init__(
            self,
            enum_cls: enum.EnumMeta,
            *args: Any,
            **kwargs: Any
    ) -> None:
        self.valid_types = (str, enum_cls)
        self.valid_strs = [elem.value for elem in enum_cls]  # type: ignore[var-annotated]
        self.enum_cls = enum_cls
        super().__init__(*args, **kwargs)

    def _serialize(
            self,
            value: Union[ApiJobKind, ApiJobStatus],
            attr: str,
            obj: BaseModel
    ) -> str:
        return value.value

    def _deserialize(
            self,
            value: Union[ApiJobKind, ApiJobStatus],
            attr: str,
            data: Dict[str, Any]
    ) -> enum.EnumMeta:
        return self.enum_cls(value)

    def check_type(
            self,
            value: Union[str, ApiJobKind, ApiJobStatus],
            attr: str,
            data: Dict[str, Any]
    ) -> None:
        # Quick check of the type
        super().check_type(value, attr, data)

        if (isinstance(value, str)) and (value not in self.valid_strs):
            raise ValidationError("{} is {}, which is not an expected value.".format(attr, value))
