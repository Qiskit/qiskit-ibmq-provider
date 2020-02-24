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
==============================================================================
Utilities (:mod:`qiskit.providers.ibmq.utils`)
==============================================================================

.. currentmodule:: qiskit.providers.ibmq.utils

Utility functions related to the IBM Quantum Provider.

Functions
=========
.. autosummary::
    :toctree: ../stubs/

    utc_to_local
"""

from .converters import utc_to_local
from .qobj_utils import update_qobj_config
from .utils import to_python_identifier, validate_job_tags
