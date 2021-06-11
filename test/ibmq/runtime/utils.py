# This code is part of Qiskit.
#
# (C) Copyright IBM 2021.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Utility functions for runtime testing."""

import json

from qiskit.providers.ibmq.runtime import ResultDecoder


def get_complex_types():
    """Return a dictionary with values of more complicated types."""
    return {"string": "foo",
            "float": 1.5,
            "complex": 2+3j,
            "serializable_class": SerializableClass("foo")}


class SerializableClass:
    """Custom class with serialization methods."""

    def __init__(self, value):
        self.value = value

    def to_json(self):
        """To JSON serializable."""
        return json.dumps({"value": self.value})

    @classmethod
    def from_json(cls, json_str):
        """From JSON serializable."""
        return cls(**json.loads(json_str))

    def __eq__(self, other):
        return self.value == other.value


class SerializableClassDecoder(ResultDecoder):
    """Decoder used for decode SerializableClass in job result."""

    @classmethod
    def decode(cls, data):
        """Decode input data."""
        decoded = super().decode(data)
        if 'serializable_class' in decoded:
            decoded['serializable_class'] = \
                SerializableClass.from_json(decoded['serializable_class'])
        return decoded


class UnserializableClass:
    """Custom class without serialization methods."""

    def __init__(self, value):
        self.value = value

    def __eq__(self, other):
        return self.value == other.value
