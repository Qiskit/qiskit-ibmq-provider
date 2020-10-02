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

Logging
=====================

The IBM Quantum Provider uses the ``qiskit.providers.ibmq`` logger.

Two environment variables can be used to control the logging:

    * ``QISKIT_IBMQ_PROVIDER_LOG_LEVEL``: Specifies the log level to use, for the
      ibmq-provider modules. If an invalid level is set, the log level defaults to ``WARNING``.
      The valid log levels are ``DEBUG``, ``INFO``, ``WARNING``, ``ERROR``, and ``CRITICAL``
      (case-insensitive). If the environment variable is not set, then the parent logger's level
      is used, which also defaults to ``WARNING``.
    * ``QISKIT_IBMQ_PROVIDER_LOG_FILE``: Specifies the name of the log file to use. If specified,
      messages will be logged to the file only. Otherwise messages will be logged to the standard
      error (usually the screen).

For more advanced use, you can modify the logger itself. For example, to manually set the level
to ``WARNING``::

    import logging
    logging.getLogger('qiskit.providers.ibmq').setLevel(logging.WARNING)

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

import logging
from typing import List, Optional
from datetime import datetime, timedelta

from .ibmqfactory import IBMQFactory
from .ibmqbackend import IBMQBackend, BaseBackend
from .job import IBMQJob
from .managed import IBMQJobManager
from .accountprovider import AccountProvider
from .backendjoblimit import BackendJobLimit
from .exceptions import *
from .ibmqbackendservice import IBMQBackendService
from .utils.utils import setup_logger

from .version import __version__

# Setup the logger for the IBM Quantum Provider package.
logger = logging.getLogger(__name__)
setup_logger(logger)

IBMQ = IBMQFactory()
"""A global instance of an account manager that is used as the entry point for convenience."""

# Constants used by the IBM Quantum logger.
IBMQ_PROVIDER_LOGGER_NAME = 'qiskit.providers.ibmq'
"""The name of the IBM Quantum logger."""
QISKIT_IBMQ_PROVIDER_LOG_LEVEL = 'QISKIT_IBMQ_PROVIDER_LOG_LEVEL'
"""The environment variable name that is used to set the level for the IBM Quantum logger."""
QISKIT_IBMQ_PROVIDER_LOG_FILE = 'QISKIT_IBMQ_PROVIDER_LOG_FILE'
"""The environment variable name that is used to set the file for the IBM Quantum logger."""


def least_busy(
        backends: List[BaseBackend],
        reservation_lookahead: Optional[int] = 60
) -> BaseBackend:
    """Return the least busy backend from a list.

    Return the least busy available backend for those that
    have a ``pending_jobs`` in their ``status``. Note that local
    backends may not have this attribute.

    Args:
        backends: The backends to choose from.
        reservation_lookahead: A backend is considered unavailable if it
            has reservations in the next ``n`` minutes, where ``n`` is
            the value of ``reservation_lookahead``.
            If ``None``, reservations are not taken into consideration.

    Returns:
        The backend with the fewest number of pending jobs.

    Raises:
        IBMQError: If the backends list is empty, or if none of the backends
            is available, or if a backend in the list
            does not have the ``pending_jobs`` attribute in its status.
    """
    if not backends:
        raise IBMQError('Unable to find the least_busy '
                        'backend from an empty list.') from None
    try:
        candidates = []
        now = datetime.now()
        for back in backends:
            if not back.status().operational:
                continue
            if reservation_lookahead and isinstance(back, IBMQBackend):
                end_time = now + timedelta(minutes=reservation_lookahead)
                try:
                    if back.reservations(now, end_time):
                        continue
                except Exception as err:  # pylint: disable=broad-except
                    logger.warning("Unable to find backend reservation information. "
                                   "It will not be taken into consideration. %s", str(err))
            candidates.append(back)
        if not candidates:
            raise IBMQError('No backend matches the criteria.')
        return min(candidates, key=lambda b: b.status().pending_jobs)
    except AttributeError as ex:
        raise IBMQError('A backend in the list does not have the `pending_jobs` '
                        'attribute in its status.') from ex
