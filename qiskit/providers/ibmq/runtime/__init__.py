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
======================================================
Runtime Service (:mod:`qiskit.providers.ibmq.runtime`)
======================================================

.. currentmodule:: qiskit.providers.ibmq.runtime

Modules related to IBM Quantum Runtime Service.

.. caution::

  This package is currently provided in beta form and heavy modifications to
  both functionality and API are likely to occur without backward compatibility.

.. note::

  The runtime service is not available to all accounts.

The IBM Quantum Runtime Service allows select users to upload their quantum programs
that can be invoked by others. A quantum program is a piece of code that takes
certain inputs, does quantum and sometimes classical processing, and returns the
results. For example, user A can upload a VQE quantum program that takes a Hamiltonian
and an optimizer as inputs and returns the minimum eigensolver result. User B
can then invoke this program, passing in the inputs and obtaining the results,
with minimal code.

These quantum programs, sometimes called runtime programs, run in a special
runtime environment that is separate from normal circuit job execution and has
special performance advantage.

TODO: Add tutorial reference

Classes
==========================
.. autosummary::
   :toctree: ../stubs/

   IBMRuntimeService
   RuntimeJob
   RuntimeProgram
   UserMessenger
   ProgramBackend
"""

from .ibm_runtime_service import IBMRuntimeService
from .runtime_job import RuntimeJob
from .runtime_program import RuntimeProgram
from .program.user_messenger import UserMessenger
from .program.program_backend import ProgramBackend
