# This code is part of Qiskit.
#
# (C) Copyright IBM 2020.
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

import json
from typing import Any, Callable, Dict
import base64
import io
import zlib
import sys
import inspect
import importlib

import numpy as np

from qiskit.result import Result
from qiskit.circuit import QuantumCircuit
from qiskit.circuit import ParameterExpression, Instruction

# TODO: remove when Terra 0.18 is released.
from qiskit.version import VERSION as terra_version
if terra_version >= "0.18":
    from qiskit.circuit import qpy_serialization


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


class SerializableClass:
    """A lazy loading wrapper to get serializable classes."""

    def __init__(self) -> None:
        """SerializableClass constructor."""
        self._classes = {"PrimitiveOp", "PauliSumOp", "PauliOp", "CircuitOp",
                         "EvolvedOp", "MatrixOp", "TaperedPauliSumOp", "Operator",
                         "Pauli", "PauliTable", "SparsePauliOp", "Z2Symmetries",
                         "StateFn", "DictStateFn", "VectorStateFn", "CircuitStateFn",
                         "OperatorStateFn", "CVaRMeasurement", "Statevector",
                         "ComposedOp", "SummedOp", "TensoredOp"
                         }
        self._mapper: Dict[str, Any] = {}

    def _load_classes(self) -> None:
        """Load all the supported classes."""
        modules = {"qiskit.opflow",
                   "qiskit.quantum_info"}
        for mod in modules:
            importlib.import_module(mod)
            for name, obj in inspect.getmembers(sys.modules[mod], inspect.isclass):
                if self.is_supported(name):
                    self._mapper[name] = obj

    def is_supported(self, class_name: str) -> bool:
        """Return whether the class is supported.

        Args:
            class_name: Name of the class.

        Returns:
            Whether the class is supported.
        """
        return class_name in self._classes

    def serialize(self, obj: Any) -> Dict:
        """Return the object in JSON serializable format."""
        name = obj.__class__.__name__
        if name in self._classes:
            return obj.settings
        raise ValueError(f"Unable to encode class {name}")

    def deserialize(self, name: str, value: Dict) -> Any:
        """Deserialize the JSON string.

        Args:
            name: Name of the class.
            value: Serialized format of the object.

        Returns:
            Deserialized object.

        Raises:
            ValueError: If the string cannot be deserialized.
        """
        if not self._mapper:
            self._load_classes()
        try:
            return self._mapper[name](**value)
        except Exception as err:
            raise ValueError(f"Unable to decode class {name}.") from err


class RuntimeEncoder(json.JSONEncoder):
    """JSON Encoder used by runtime service."""

    def default(self, obj: Any) -> Any:  # pylint: disable=arguments-differ
        if isinstance(obj, complex):
            return {'__type__': 'complex', '__value__': [obj.real, obj.imag]}
        if isinstance(obj, np.ndarray):
            value = _serialize_and_encode(obj, np.save, allow_pickle=False)
            return {'__type__': 'ndarray', '__value__': value}
        if isinstance(obj, set):
            return {'__type__': 'set', '__value__': list(obj)}
        if isinstance(obj, Result):
            return {'__type__': 'Result', '__value__': obj.to_dict()}
        if hasattr(obj, 'to_json'):
            return {'__type__': 'to_json', '__value__': obj.to_json()}

        # TODO: remove when Terra 0.18 is released.
        if terra_version < "0.18":
            return super().default(obj)

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
            value = _serialize_and_encode(
                data=obj, serializer=qpy_serialization._write_instruction, compress=False)
            return {'__type__': 'Instruction', '__value__': value}

        serializer = SerializableClass()
        if serializer.is_supported(obj.__class__.__name__):
            return {'__type__': obj.__class__.__name__, '__value__': serializer.serialize(obj)}

        return super().default(obj)


class RuntimeDecoder(json.JSONDecoder):
    """JSON Decoder used by runtime service."""

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(object_hook=self.object_hook, *args, **kwargs)

    def object_hook(self, obj: Any) -> Any:
        """Called to decode object."""
        if '__type__' in obj:
            obj_type = obj['__type__']
            obj_val = obj['__value__']

            if obj_type == 'complex':
                return obj_val[0] + 1j * obj_val[1]
            if obj_type == 'ndarray':
                return _decode_and_deserialize(obj_val, np.load)
            if obj_type == 'set':
                return set(obj_val)
            if obj_type == 'QuantumCircuit':
                return _decode_and_deserialize(obj_val, qpy_serialization.load)[0]
            if obj_type == 'ParameterExpression':
                return _decode_and_deserialize(
                    obj_val, qpy_serialization._read_parameter_expression, False)
            if obj_type == 'Instruction':
                return _decode_and_deserialize(
                    obj_val, qpy_serialization._read_instruction, False)
            serializer = SerializableClass()
            if serializer.is_supported(obj_type):
                return serializer.deserialize(obj_type, obj_val)
            if obj_type == 'Result':
                return Result.from_dict(obj_val)
            if obj_type == 'to_json':
                return obj_val
        return obj
