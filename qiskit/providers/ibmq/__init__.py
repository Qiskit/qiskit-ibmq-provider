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

"""Backends provided by IBM Quantum Experience."""

import warnings
from typing import List

from qiskit.exceptions import QiskitError
from .ibmqfactory import IBMQFactory
from .ibmqbackend import IBMQBackend, BaseBackend
from .job import IBMQJob

from .version import __version__

# Global instance to be used as the entry point for convenience.
IBMQ = IBMQFactory()


def least_busy(backends: List[BaseBackend]) -> BaseBackend:
    """Return the least busy backend from a list.

    Return the least busy available backend for those that
    have a `pending_jobs` in their `status`. Backends such as
    local backends that do not have this are not considered.

    Args:
        backends (list[BaseBackend]): backends to choose from

    Returns:
        BaseBackend: the the least busy backend

    Raises:
        QiskitError: if passing a list of backend names that is
            either empty or none have attribute ``pending_jobs``
    """
    try:
        return min([b for b in backends if b.status().operational],
                   key=lambda b: b.status().pending_jobs)
    except (ValueError, TypeError):
        raise QiskitError("Can only find least_busy backend from a non-empty list.")


def formatwarning(message, category, filename, lineno, line):
    """Function to format a warning the standard way.

    By default, the message `warnings.warn()` displays includes the
    *exact* line that issues a warning (i.e. the warnings.warn() call
    itself). A downfall to this is when the message passed as argument to
    `warnings.warn()` extends past one line, because it cuts off the
    message and only includes the part that is on the *exact* line as
    the `warnings.warn()` call.

        Example:
            When the message is passed in the following format:

                warnings.warn('This is a message that
                              'that extends two lines')

            the only part included in the final warning to the user is:

                warnings.warn('This is a message that

            and "that extends two lines" is cut off, since it is not
            on the *exact* same line that issued the warning.

    This function displays the same message `warnings.formatwarning`
    displays, minus the `line` that issues the warning, which is not
    necessary since the exact line number and location of the warning
    are printed as well.
    """
    return "%s:%s: %s: %s %s\n" % (filename, lineno, category.__name__, message, line or '')


# Set custom warning message formatter for `warnings.warn()`.
warnings.formatwarning = formatwarning
