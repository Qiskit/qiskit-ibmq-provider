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


def most_busy_backend(provider):
    """Return the most busy backend for the provider given.

    Return the most busy available backend for those that
    have a `pending_jobs` in their `status`. Backends such as
    local backends that do not have this are not considered.

    Args:
        provider (AccountProvider): IBM Q Experience account provider.

    Returns:
        IBMQBackend: the most busy backend.
    """
    backends = provider.backends(simulator=False, operational=True)
    return max([b for b in backends if b.configuration().n_qubits >= 5],
               key=lambda b: b.status().pending_jobs)
