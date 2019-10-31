# -*- coding: utf-8 -*-

# This code is part of Qiskit.
#
# (C) Copyright IBM 2018, 2019.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Exceptions related to Circuits."""

from typing import Any

from ..exceptions import IBMQError, IBMQErrorCodes


CIRCUIT_NOT_ALLOWED = 'Circuit support is not available yet in this account'
CIRCUIT_SUBMIT_ERROR = 'Circuit could not be submitted: {}'
CIRCUIT_RESULT_ERROR = 'Circuit result could not be returned: {}'


class CircuitError(IBMQError):
    """Generic Circuit exception."""

    def __init__(self, *message: Any) -> None:
        """Set the error message and code."""
        super().__init__(*message, error_code=IBMQ_CIRCUIT_ERROR_CODES[type(self)])


class CircuitAvailabilityError(CircuitError):
    """Error while accessing a Circuit."""

    def __init__(self, message: str = ''):
        super().__init__(message or CIRCUIT_NOT_ALLOWED)


class CircuitSubmitError(CircuitError):
    """Error while submitting a Circuit."""

    def __init__(self, message: str):
        super().__init__(CIRCUIT_SUBMIT_ERROR.format(message))


class CircuitResultError(CircuitError):
    """Error during the results of a Circuit."""

    def __init__(self, message: str):
        super().__init__(CIRCUIT_RESULT_ERROR.format(message))


IBMQ_CIRCUIT_ERROR_CODES = {
    CircuitError: IBMQErrorCodes.GENERIC_CIRCUITS_ERROR,
    CircuitAvailabilityError: IBMQErrorCodes.CIRCUITS_NOT_AVAILABLE,
    CircuitSubmitError: IBMQErrorCodes.GENERIC_CIRCUITS_ERROR,
    CircuitResultError: IBMQErrorCodes.GENERIC_CIRCUITS_ERROR
}
