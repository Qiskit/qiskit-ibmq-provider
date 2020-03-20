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
    IQXBackend
    IQXBackendService
    IQXFactory

Exceptions
==========
.. autosummary::
    :toctree: ../stubs/

    IQXError
    IQXAccountError
    IQXAccountCredentialsNotFound
    IQXAccountCredentialsInvalidFormat
    IQXAccountCredentialsInvalidToken
    IQXAccountCredentialsInvalidUrl
    IQXAccountMultipleCredentialsFound
    IQXBackendError
    IQXBackendApiError
    IQXBackendApiProtocolError
    IQXBackendValueError
    IQXProviderError
"""

import logging
from typing import List

from .iqxfactory import IQXFactory
from .iqxbackend import IQXBackend, BaseBackend
from .job import IQXJob
from .managed import IQXJobManager
from .accountprovider import AccountProvider
from .backendjoblimit import BackendJobLimit
from .exceptions import *
from .iqxbackendservice import IQXBackendService
from .utils.utils import setup_logger

from .version import __version__

# Setup the logger for the IBM Quantum Provider package.
logger = logging.getLogger(__name__)
setup_logger(logger)

IQX = IQXFactory()
"""A global instance of an account manager that is used as the entry point for convenience."""

# Constants used by the IBM Quantum logger.
IQX_PROVIDER_LOGGER_NAME = 'qiskit.providers.ibmq'
"""The name of the IBM Quantum logger."""
QISKIT_IQX_PROVIDER_LOG_LEVEL = 'QISKIT_IQX_PROVIDER_LOG_LEVEL'
"""The environment variable name that is used to set the level for the IBM Quantum logger."""
QISKIT_IQX_PROVIDER_LOG_FILE = 'QISKIT_IQX_PROVIDER_LOG_FILE'
"""The environment variable name that is used to set the file for the IBM Quantum logger."""


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
        IQXError: If the backends list is empty or if a backend in the list
            does not have the ``pending_jobs`` attribute in its status.
    """
    try:
        return min([b for b in backends if b.status().operational],
                   key=lambda b: b.status().pending_jobs)
    except (ValueError, TypeError):
        raise IQXError('Unable to find the least_busy '
                       'backend from an empty list.') from None
    except AttributeError as ex:
        raise IQXError('A backend in the list does not have the `pending_jobs` '
                       'attribute in its status.') from ex
