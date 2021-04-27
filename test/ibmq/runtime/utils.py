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

"""Utility functions for runtime testing."""

import json


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


class UnserializableClass:
    """Custom class without serialization methods."""

    def __init__(self, value):
        self.value = value

    def __eq__(self, other):
        return self.value == other.value
