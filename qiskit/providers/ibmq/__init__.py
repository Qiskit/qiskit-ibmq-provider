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

You are able to change its level manually or via the environment variable
``QISKIT_IBMQ_PROVIDER_LOG_LEVEL``. Likewise, you are able to specify a file
to log the messages to with the environment variable ``QISKIT_IBMQ_PROVIDER_LOG_FILE``.

To change the level manually, simply grab the logger and set its level::

    import logging
    logging.getLogger('qiskit.providers.ibmq').setLevel(logging.WARNING)

Details pertaining to the environment variables used by the logger:

    * ``QISKIT_IBMQ_PROVIDER_LOG_LEVEL``: Specifies the log level to use, for the
      provider modules, when logging. If an invalid level is set, the log level defaults
      to ``WARNING``. The valid log levels are ``DEBUG``, ``INFO``, ``WARNING``, ``ERROR``,
      and ``CRITICAL`` (case-insensitive). If the environment variable is not set, then
      the parent logger's level is used, which also defaults to `WARNING`.
    * ``QISKIT_IBMQ_PROVIDER_LOG_FILE``: Specifies the name of the logfile to use when logging
      messages. If specified, the log messages will be logged to the file but not to the screen.
      If it is not specified, the log messages will only be logged to the screen.

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
from typing import List

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
        IBMQError: If the backends list is empty or if a backend in the list
            does not have the ``pending_jobs`` attribute in its status.
    """
    try:
        return min([b for b in backends if b.status().operational],
                   key=lambda b: b.status().pending_jobs)
    except (ValueError, TypeError):
        raise IBMQError('Unable to find the least_busy '
                        'backend from an empty list.') from None
    except AttributeError as ex:
        raise IBMQError('A backend in the list does not have the `pending_jobs` '
                        'attribute in its status.') from ex
