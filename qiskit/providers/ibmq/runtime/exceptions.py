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

"""Exceptions related to IBM Quantum runtime service."""


from ..exceptions import IBMQError


class QiskitRuntimeError(IBMQError):
    """Base class for errors raised by the runtime service modules."""
    pass


class RuntimeDuplicateProgramError(QiskitRuntimeError):
    """Error raised when a program being uploaded already exists."""
    pass


class RuntimeProgramNotFound(QiskitRuntimeError):
    """Error raised when a program is not found."""
    pass


class RuntimeJobFailureError(QiskitRuntimeError):
    """Error raised when a runtime job failed."""
    pass


class RuntimeJobNotFound(QiskitRuntimeError):
    """Error raised when a job is not found."""
    pass


class RuntimeInvalidStateError(QiskitRuntimeError):
    """Errors raised when the state is not valid for the operation."""
    pass
