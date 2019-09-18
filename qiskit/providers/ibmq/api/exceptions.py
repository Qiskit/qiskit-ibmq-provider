# -*- coding: utf-8 -*-

# This code is part of Qiskit.
#
# (C) Copyright IBM 2017, 2018.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Exceptions for IBMQ Connector."""

from ..exceptions import IBMQError


class ApiError(IBMQError):
    """IBMQConnector API error handling base class."""

    def __init__(self, usr_msg=None, dev_msg=None):
        """ApiError.

        Args:
            usr_msg (str): Short user facing message describing error.
            dev_msg (str or None): More detailed message to assist
                developer with resolving issue.
        """
        super().__init__(usr_msg)
        self.usr_msg = usr_msg
        self.dev_msg = dev_msg

    def __repr__(self):
        return repr(self.dev_msg)

    def __str__(self):
        return str(self.usr_msg)


class BadBackendError(ApiError):
    """Unavailable backend error."""

    def __init__(self, backend):
        """BadBackendError.

        Args:
            backend (str): name of backend.
        """
        usr_msg = 'Could not find backend "{0}" available.'.format(backend)
        dev_msg = ('Backend "{0}" does not exist. Please use '
                   'available_backends to see options').format(backend)
        super().__init__(usr_msg, dev_msg)


class CredentialsError(ApiError):
    """Exception associated with bad server credentials."""
    pass


class RegisterSizeError(ApiError):
    """Exception due to exceeding the maximum number of allowed qubits."""
    pass
