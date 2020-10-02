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

"""
============================================================
Random Number Services (:mod:`qiskit.providers.ibmq.random`)
============================================================

.. currentmodule:: qiskit.providers.ibmq.random

Modules related to IBM Quantum Experience random number generator services.

.. caution::

  This package is currently provided in beta form and heavy modifications to
  both functionality and API are likely to occur.

The only service currently provided is the Cambridge Quantum Computing (CQC)
extractor. To use this service, you need to first generate raw random bits
and a set of parameters for the extractor. See
`qiskit_rng <https://github.com/qiskit-community/qiskit_rng>`_ for more
details.

.. note::

  The CQC extractor service is not available to all accounts.

Classes
==========================
.. autosummary::
   :toctree: ../stubs/

   IBMQRandomService
   CQCExtractor
   CQCExtractorJob

"""

from .ibmqrandomservice import IBMQRandomService
from .cqcextractor import CQCExtractor
from .cqcextractorjob import CQCExtractorJob
