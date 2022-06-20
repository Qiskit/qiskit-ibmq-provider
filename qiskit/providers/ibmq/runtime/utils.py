# This code is part of Qiskit.
#
# (C) Copyright IBM 2020, 2021.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.
# pylint: disable=method-hidden
# pylint: disable=too-many-return-statements

"""Utility functions for the runtime service."""

import base64
import copy
import functools
import importlib
import inspect
import io
import json
import re
import warnings
import zlib
from datetime import date
from typing import Any, Callable, Dict, List, Union, Tuple

import dateutil.parser
import numpy as np

try:
    import scipy.sparse
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False

from qiskit.circuit import (
    Instruction,
    ParameterExpression,
    ParameterVector,
    QuantumCircuit,
    QuantumRegister,
    qpy_serialization,
)
from qiskit.result import Result

from qiskit.version import __version__ as _terra_version_string


# This version pattern is taken from the pypa packaging project:
# https://github.com/pypa/packaging/blob/21.3/packaging/version.py#L223-L254
# which is dual licensed Apache 2.0 and BSD see the source for the original
# authors and other details
VERSION_PATTERN = (
    "^"
    + r"""
    v?
    (?:
        (?:(?P<epoch>[0-9]+)!)?                           # epoch
        (?P<release>[0-9]+(?:\.[0-9]+)*)                  # release segment
        (?P<pre>                                          # pre-release
            [-_\.]?
            (?P<pre_l>(a|b|c|rc|alpha|beta|pre|preview))
            [-_\.]?
            (?P<pre_n>[0-9]+)?
        )?
        (?P<post>                                         # post release
            (?:-(?P<post_n1>[0-9]+))
            |
            (?:
                [-_\.]?
                (?P<post_l>post|rev|r)
                [-_\.]?
                (?P<post_n2>[0-9]+)?
            )
        )?
        (?P<dev>                                          # dev release
            [-_\.]?
            (?P<dev_l>dev)
            [-_\.]?
            (?P<dev_n>[0-9]+)?
        )?
    )
    (?:\+(?P<local>[a-z0-9]+(?:[-_\.][a-z0-9]+)*))?       # local version
"""
    + "$"
)
_TERRA_VERSION = tuple(
    int(x) for x in re.search(
        VERSION_PATTERN,
        _terra_version_string,
        re.VERBOSE | re.IGNORECASE
    ).group("release").split(".")
)


def to_base64_string(data: str) -> str:
    """Convert string to base64 string.

    Args:
        data: string to convert

    Returns:
        data as base64 string
    """
    return base64.b64encode(data.encode('utf-8')).decode('utf-8')


def _serialize_and_encode(
        data: Any,
        serializer: Callable,
        compress: bool = True,
        **kwargs: Any
) -> str:
    """Serialize the input data and return the encoded string.

    Args:
        data: Data to be serialized.
        serializer: Function used to serialize data.
        compress: Whether to compress the serialized data.
        kwargs: Keyword arguments to pass to the serializer.

    Returns:
        String representation.
    """
    buff = io.BytesIO()
    serializer(buff, data, **kwargs)
    buff.seek(0)
    serialized_data = buff.read()
    buff.close()
    if compress:
        serialized_data = zlib.compress(serialized_data)
    return base64.standard_b64encode(serialized_data).decode("utf-8")


def _decode_and_deserialize(data: str, deserializer: Callable, decompress: bool = True) -> Any:
    """Decode and deserialize input data.

    Args:
        data: Data to be deserialized.
        deserializer: Function used to deserialize data.
        decompress: Whether to decompress.

    Returns:
        Deserialized data.
    """
    buff = io.BytesIO()
    decoded = base64.standard_b64decode(data)
    if decompress:
        decoded = zlib.decompress(decoded)
    buff.write(decoded)
    buff.seek(0)
    orig = deserializer(buff)
    buff.close()
    return orig


def deserialize_from_settings(mod_name: str, class_name: str, settings: Dict) -> Any:
    """Deserialize an object from its settings.

    Args:
        mod_name: Name of the module.
        class_name: Name of the class.
        settings: Object settings.

    Returns:
        Deserialized object.

    Raises:
        ValueError: If unable to find the class.
    """
    mod = importlib.import_module(mod_name)
    for name, clz in inspect.getmembers(mod, inspect.isclass):
        if name == class_name:
            return clz(**settings)
    raise ValueError(f"Unable to find class {class_name} in module {mod_name}")


def _set_int_keys_flag(obj: Dict) -> Union[Dict, List]:
    """Recursively sets '__int_keys__' flag if dictionary uses integer keys

    Args:
        obj: dictionary

    Returns:
        obj with the '__int_keys__' flag set if dictionary uses integer key
    """
    if isinstance(obj, dict):
        for k, v in list(obj.items()):
            if isinstance(k, int):
                obj['__int_keys__'] = True
            _set_int_keys_flag(v)
    return obj


def _cast_strings_keys_to_int(obj: Dict) -> Dict:
    """Casts string to int keys in dictionary when '__int_keys__' flag is set

    Args:
        obj: dictionary

    Returns:
        obj with string keys cast to int keys and '__int_keys__' flags removed
    """
    if isinstance(obj, dict):
        int_keys: List[int] = []
        for k, v in list(obj.items()):
            if '__int_keys__' in obj:
                try:
                    int_keys.append(int(k))
                except ValueError:
                    pass
            _cast_strings_keys_to_int(v)
        while len(int_keys) > 0:
            key = int_keys.pop()
            obj[key] = obj[str(key)]
            obj.pop(str(key))
        if '__int_keys__' in obj:
            del obj['__int_keys__']
    return obj


class RuntimeEncoder(json.JSONEncoder):
    """JSON Encoder used by runtime service."""

    def default(self, obj: Any) -> Any:  # pylint: disable=arguments-differ
        if isinstance(obj, date):
            return {'__type__': 'datetime', '__value__': obj.isoformat()}
        if isinstance(obj, complex):
            return {'__type__': 'complex', '__value__': [obj.real, obj.imag]}
        if isinstance(obj, np.ndarray):
            if obj.dtype == object:
                return {"__type__": "ndarray", "__value__": obj.tolist()}
            value = _serialize_and_encode(obj, np.save, allow_pickle=False)
            return {'__type__': 'ndarray', '__value__': value}
        if isinstance(obj, set):
            return {'__type__': 'set', '__value__': list(obj)}
        if isinstance(obj, Result):
            return {'__type__': 'Result', '__value__': obj.to_dict()}
        if hasattr(obj, 'to_json'):
            return {'__type__': 'to_json', '__value__': obj.to_json()}
        if isinstance(obj, QuantumCircuit):
            value = _serialize_and_encode(
                data=obj,
                serializer=lambda buff, data: qpy_serialization.dump(data, buff)
            )
            return {'__type__': 'QuantumCircuit', '__value__': value}
        if isinstance(obj, ParameterExpression):
            value = _serialize_and_encode(
                data=obj,
                serializer=qpy_serialization._write_parameter_expression,
                compress=False,
            )
            return {'__type__': 'ParameterExpression', '__value__': value}
        if isinstance(obj, Instruction):
            # Append instruction to empty circuit
            quantum_register = QuantumRegister(obj.num_qubits)
            quantum_circuit = QuantumCircuit(quantum_register)
            quantum_circuit.append(obj, quantum_register)
            value = _serialize_and_encode(
                data=quantum_circuit,
                serializer=lambda buff, data: qpy_serialization.dump(data, buff))
            return {'__type__': 'Instruction', '__value__': value}
        if hasattr(obj, "settings"):
            return {'__type__': 'settings',
                    '__module__': obj.__class__.__module__,
                    '__class__': obj.__class__.__name__,
                    '__value__': _set_int_keys_flag(copy.deepcopy(obj.settings))}
        if callable(obj):
            warnings.warn(f"Callable {obj} is not JSON serializable and will be set to None.")
            return None
        if HAS_SCIPY and isinstance(obj, scipy.sparse.spmatrix):
            value = _serialize_and_encode(obj, scipy.sparse.save_npz, compress=False)
            return {'__type__': 'spmatrix', '__value__': value}
        return super().default(obj)


class RuntimeDecoder(json.JSONDecoder):
    """JSON Decoder used by runtime service."""

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(object_hook=self.object_hook, *args, **kwargs)
        self.__parameter_vectors: Dict[str, Tuple[ParameterVector, set]] = {}
        self.__read_parameter_expression = (
            functools.partial(
                qpy_serialization._read_parameter_expression_v3,
                vectors=self.__parameter_vectors,
            )
            if _TERRA_VERSION >= (0, 19, 1)
            else qpy_serialization._read_parameter_expression
        )

    def object_hook(self, obj: Any) -> Any:
        """Called to decode object."""
        if '__type__' in obj:
            obj_type = obj['__type__']
            obj_val = obj['__value__']

            if obj_type == 'datetime':
                return dateutil.parser.parse(obj_val)
            if obj_type == 'complex':
                return obj_val[0] + 1j * obj_val[1]
            if obj_type == 'ndarray':
                if isinstance(obj_val, list):
                    return np.array(obj_val)
                return _decode_and_deserialize(obj_val, np.load)
            if obj_type == 'set':
                return set(obj_val)
            if obj_type == 'QuantumCircuit':
                return _decode_and_deserialize(obj_val, qpy_serialization.load)[0]
            if obj_type == 'ParameterExpression':
                return _decode_and_deserialize(
                    obj_val, self.__read_parameter_expression, False
                )
            if obj_type == "Instruction":
                # Standalone instructions are encoded as the sole
                # instruction in a QPY serialized circuit to deserialize
                # load qpy circuit and return first instruction object in that circuit.
                circuit = _decode_and_deserialize(obj_val, qpy_serialization.load)[0]
                return circuit.data[0][0]
            if obj_type == 'settings':
                return deserialize_from_settings(
                    mod_name=obj['__module__'],
                    class_name=obj['__class__'],
                    settings=_cast_strings_keys_to_int(obj_val)
                )
            if obj_type == 'Result':
                return Result.from_dict(obj_val)
            if obj_type == 'spmatrix':
                return _decode_and_deserialize(obj_val, scipy.sparse.load_npz, False)
            if obj_type == 'to_json':
                return obj_val
        return obj
