# This code is part of Qiskit.
#
# (C) Copyright IBM 2021.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""
============================================================
Runtime Service (:mod:`qiskit.providers.ibmq.runtime`)
============================================================

.. currentmodule:: qiskit.providers.ibmq.runtime

Modules related to IBM Quantum Experience runtime service.

.. caution::

  This package is currently provided in beta form and heavy modifications to
  both functionality and API are likely to occur.

.. note::

  The runtime service is not available to all accounts.

Classes
==========================
.. autosummary::
   :toctree: ../stubs/

   IBMRuntimeService
   RuntimeJob

"""

from .ibm_runtime_service import IBMRuntimeService
from .runtime_job import RuntimeJob
