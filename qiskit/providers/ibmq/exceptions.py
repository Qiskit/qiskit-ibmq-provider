# -*- coding: utf-8 -*-

# This code is part of Qiskit.
#
# (C) Copyright IBM 2018.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Exception for the IBMQ module."""

from qiskit.exceptions import QiskitError


class IBMQError(QiskitError):
    """Base class for errors raised by the IBMQ provider module."""
    pass


class IBMQAccountError(IBMQError):
    """Base class for errors raised by account management."""
    pass


class IBMQBackendError(IBMQError):
    """IBM Q Backend Errors"""
    pass


class IBMQBackendValueError(IBMQError, ValueError):
    """Value errors thrown within IBMQBackend """
    pass
