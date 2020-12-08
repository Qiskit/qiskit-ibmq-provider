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
====================================================
Experiment (:mod:`qiskit.providers.ibmq.experiment`)
====================================================

.. currentmodule:: qiskit.providers.ibmq.experiment

Modules representing IBM Quantum Experience experiments.

.. caution::

  This package is currently provided in beta form and heavy modifications to
  both functionality and API are likely to occur.

.. note::

  This service is not available to all accounts.

You can use the experiment service to query, upload, and retrieve
experiments, experiment plots, and analysis results. For example::

    from qiskit import IBMQ
    provider = IBMQ.load_account()
    experiments = provider.experiment.experiments()

All the available functions can be invoked using the `provider.experiment`
attribute, which is an instance of the
:class:`~qiskit.providers.ibmq.experiment.ExperimentService` class.

Classes
=========

.. autosummary::
    :toctree: ../stubs/

    ExperimentService
    Experiment
    AnalysisResult
"""

from .experimentservice import ExperimentService
from .experiment import Experiment
from .analysis_result import AnalysisResult
