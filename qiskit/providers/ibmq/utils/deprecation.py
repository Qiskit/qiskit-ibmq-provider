# -*- coding: utf-8 -*-

# This code is part of Qiskit.
#
# (C) Copyright IBM 2017, 2019.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Utilities for transitioning from IBM Q Experience v1 to v2."""

import warnings
from functools import wraps

from qiskit.providers.ibmq.exceptions import IBMQAccountError

UPDATE_ACCOUNT_TEXT = (
    'Please update your accounts and programs by following the instructions here:\n'
    'https://github.com/Qiskit/qiskit-ibmq-provider#updating-to-the-new-ibm-q-experience')


def deprecated(func):
    """Decorator that signals that the function has been deprecated.

    Args:
        func (callable): function to be decorated.

    Returns:
        callable: the decorated function.
    """

    @wraps(func)
    def _wrapper(self, *args, **kwargs):
        # The special case of load_accounts is here for backward
        # compatibility when using v2 credentials.
        if self._credentials and func.__name__ != 'load_accounts':
            raise IBMQAccountError(
                'IBMQ.{}() is not available when using an IBM Q Experience '
                'v2 account. Please use IBMQ.{}() (note the singular form) '
                'instead.'.format(func.__name__, func.__name__[:-1]))

        warnings.warn(
            'IBMQ.{}() is being deprecated. Please use IBM Q Experience v2 '
            'credentials and IBMQ.{}() (note the singular form) instead. You can '
            'find the instructions to make the updates here: \n'
            'https://github.com/Qiskit/qiskit-ibmq-provider#updating-to-the-new-ibm-q-experience'
            .format(func.__name__, func.__name__[:-1]),
            DeprecationWarning)
        return func(self, *args, **kwargs)

    return _wrapper
