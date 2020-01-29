# -*- coding: utf-8 -*-

# This code is part of Qiskit.
#
# (C) Copyright IBM 2020.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""General utility functions for testing."""

from qiskit.exceptions import QiskitError


def most_busy_backend(provider):
    """Return the most busy backend for the provider given.

    Return the most busy available backend for those that
    have a `pending_jobs` in their `status`. Backends such as
    local backends that do not have this are not considered.

    Args:
        provider (AccountProvider): IBM Q Experience account provider.

    Returns:
        IBMQBackend: the most busy backend.

    Raises:
        QiskitError: if passing a list of backend names that is
            either empty or none have attribute ``pending_jobs``
    """
    try:
        return max([b for b in provider.backends(simulator=False) if b.status().operational],
                   key=lambda b: b.status().pending_jobs)
    except (ValueError, TypeError):
        raise QiskitError("Can only find most busy backend from a non-empty list.")
