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

"""
===================================================
IBM Quantum Provider (:mod:`qiskit.providers.ibmq`)
===================================================

.. currentmodule:: qiskit.providers.ibmq

Modules representing the IBM Quantum Provider.

Functions
=========
.. autosummary::
    :toctree: ../stubs/

    least_busy

Classes
=======
.. autosummary::
    :toctree: ../stubs/

    AccountProvider
    BackendJobLimit
    IBMQBackend
    IBMQBackendService
    IBMQFactory

Exceptions
==========
.. autosummary::
    :toctree: ../stubs/

    IBMQError
    IBMQAccountError
    IBMQAccountCredentialsNotFound
    IBMQAccountCredentialsInvalidFormat
    IBMQAccountCredentialsInvalidToken
    IBMQAccountCredentialsInvalidUrl
    IBMQAccountMultipleCredentialsFound
    IBMQBackendError
    IBMQBackendApiError
    IBMQBackendApiProtocolError
    IBMQBackendValueError
    IBMQProviderError
"""

from typing import List

from .ibmqfactory import IBMQFactory
from .ibmqbackend import IBMQBackend, BaseBackend
from .job import IBMQJob
from .managed import IBMQJobManager
from .accountprovider import AccountProvider
from .backendjoblimit import BackendJobLimit
from .exceptions import *
from .ibmqbackendservice import IBMQBackendService

from .version import __version__

IBMQ = IBMQFactory()
"""A global instance of an account manager that is used as the entry point for convenience."""


def least_busy(backends: List[BaseBackend]) -> BaseBackend:
    """Return the least busy backend from a list.

    Return the least busy available backend for those that
    have a ``pending_jobs`` in their ``status``. Note that local
    backends may not have this attribute.

    Args:
        backends: The backends to choose from.

    Returns:
        The backend with the fewest number of pending jobs.

    Raises:
        QiskitError: If the backends list is empty.
        AttributeError: If a backend in the list does not have the ``pending_jobs``
            attribute in its status.
    """
    try:
        return min([b for b in backends if b.status().operational],
                   key=lambda b: b.status().pending_jobs)
    except (ValueError, TypeError):
        raise QiskitError('Can only find least_busy backend from a non-empty list.')
    except AttributeError:
        raise QiskitError('A backend in the list does not have the `pending_jobs` '
                          'attribute in its status.')
