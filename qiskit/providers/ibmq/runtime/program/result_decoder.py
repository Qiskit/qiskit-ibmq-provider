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

from qiskit.providers.ibmq.runtime.utils import RuntimeDecoder


class ResultDecoder:
    """Runtime job result decoder.

    You can subclass this class and overwrite the :meth:`decode` method
    to create a custom result decoder for the
    results of your runtime program. For example::

        class MyResultDecoder(ResultDecoder):

            @classmethod
            def decode(cls, data):
                decoded = super().decode(data)
                custom_processing(decoded)  # perform custom processing

    Users of your program will need to pass in the subclass when invoking
    :meth:`qiskit.providers.ibmq.runtime.RuntimeJob.result` or
    :meth:`qiskit.providers.ibmq.runtime.IBMRuntimeService.run`.
    """

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
