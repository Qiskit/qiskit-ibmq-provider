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

"""Qiskit runtime job result decoder."""

import json
from typing import Any

from .utils import RuntimeDecoder


class ResultDecoder:
    """Runtime job result decoder."""

    @classmethod
    def decode(cls, data: str) -> Any:
        """Decode the result data.

        Args:
            data: Result data to be decoded.

        Returns:
            Decoded result data.
        """
        try:
            return json.loads(data, cls=RuntimeDecoder)
        except json.JSONDecodeError:
            return data
