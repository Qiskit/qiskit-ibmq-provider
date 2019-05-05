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

"""Exceptions related to Qcircuits."""

from qiskit.providers.ibmq.exceptions import IBMQError


QCIRCUIT_NOT_ALLOWED = 'Qcircuit support is not available yet in this account'
QCIRCUIT_SUBMIT_ERROR = 'Qcircuit could not be submitted: {}'
QCIRCUIT_RESULT_ERROR = 'Qcircuit result could not be returned: {}'


class QcircuitError(IBMQError):
    """Generic Qcircuit exception."""
    pass


class QcircuitAvailabilityError(QcircuitError):
    """Error while accessing a Qcircuit."""

    def __init__(self, message=''):
        super().__init__(message or QCIRCUIT_NOT_ALLOWED)


class QcircuitSubmitError(QcircuitError):
    """Error while submitting a Qcircuit."""

    def __init__(self, message):
        super().__init__(QCIRCUIT_SUBMIT_ERROR.format(message))


class QcircuitResultError(QcircuitError):
    """Error during the results of a Qcircuit."""

    def __init__(self, message):
        super().__init__(QCIRCUIT_RESULT_ERROR.format(message))
