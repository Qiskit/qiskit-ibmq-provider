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
===========================================================
Job Manager (:mod:`qiskit.providers.ibmq.managed`)
===========================================================

.. currentmodule:: qiskit.providers.ibmq.managed

High level mechanism for handling jobs.

Classes
==========================
.. autosummary::
   :toctree: ../stubs/

   IBMQJobManager
   ManagedJobSet
   ManagedJob
   ManagedResults

Exceptions
==========================
.. autosummary::
   :toctree: ../stubs/

   IBMQJobManagerError
   IBMQJobManagerInvalidStateError
   IBMQJobManagerTimeoutError
   IBMQJobManagerJobNotFound
   IBMQManagedResultDataNotAvailable
   IBMQJobManagerUnknownJobSet
"""

from .ibmqjobmanager import IBMQJobManager
from .managedjobset import ManagedJobSet
from .managedjob import ManagedJob
from .managedresults import ManagedResults
from .exceptions import *
