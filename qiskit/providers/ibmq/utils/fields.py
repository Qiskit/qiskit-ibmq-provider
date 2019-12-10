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
from typing import Dict, Any

from qiskit.validation import ModelTypeValidator, BaseModel

from .utils import to_python_identifier


class Enum(ModelTypeValidator):
    """Field for enums."""

    default_error_messages = {
        'invalid': '"{input}" cannot be parsed as a {enum_cls}.',
        'format': '"{input}" cannot be formatted as a {enum_cls}.',
    }

    def __init__(self, enum_cls: enum.EnumMeta, *args: Any, **kwargs: Any) -> None:
        self.valid_types = (enum_cls,)
        self.valid_strs = [elem.value for elem in enum_cls]  # type: ignore[var-annotated]
        self.enum_cls = enum_cls

        super().__init__(*args, **kwargs)

    def _serialize(  # type: ignore[return]
            self,
            value: Any,
            attr: str,
            obj: BaseModel,
            **_: Any
    ) -> str:
        try:
            return value.value
        except AttributeError:
            # TODO: change to self.make_error_serialize after #3228
            self.make_error('format', input=value, enum_cls=self.enum_cls)

    def _deserialize(  # type: ignore[return]
            self,
            value: Any,
            attr: str,
            data: Dict[str, Any],
            **_: Any
    ) -> enum.EnumMeta:
        try:
            return self.enum_cls(value)
        except ValueError:
            self.fail('invalid', input=value, enum_cls=self.enum_cls)


def map_field_names(mapper: dict, data: dict) -> dict:
    """Rename selected fields due to name clashes, and convert from camel-case
    the rest of the fields.
    """
    rename_map = {}
    for field_name in data:
        if field_name in mapper:
            rename_map[field_name] = mapper[field_name]
        else:
            rename_map[field_name] = to_python_identifier(field_name)

    for old_name, new_name in rename_map.items():
        data[new_name] = data.pop(old_name)

    return data
