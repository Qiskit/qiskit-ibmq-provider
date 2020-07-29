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

"""
==============================================
Backend (:mod:`qiskit.providers.ibmq.backend`)
==============================================

.. currentmodule:: qiskit.providers.ibmq.backend

Modules representing IBM Quantum Experience backends.

Classes
=========

.. autosummary::
    :toctree: ../stubs/

    BackendJobLimit
    IBMQBackend
    IBMQBackendService

Exception
=========
.. autosummary::
    :toctree: ../stubs/

    IBMQBackendError
    IBMQBackendApiError
    IBMQBackendApiProtocolError
    IBMQBackendValueError
    IBMQBackendJobLimitError
"""

from .backendjoblimit import BackendJobLimit
from .ibmqbackend import IBMQBackend
from .ibmqbackendservice import IBMQBackendService

from .exceptions import *
