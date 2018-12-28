# -*- coding: utf-8 -*-

# Copyright 2018, IBM.
#
# This source code is licensed under the Apache License, Version 2.0 found in
# the LICENSE.txt file in the root directory of this source tree.

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
