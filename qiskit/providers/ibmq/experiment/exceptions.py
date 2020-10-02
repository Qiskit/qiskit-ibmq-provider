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

"""Exceptions related to IBM Quantum Experience experiments."""


from ..exceptions import IBMQError


class ExperimentError(IBMQError):
    """Base class for errors raised by the experiment modules."""
    pass


class ExperimentNotFoundError(ExperimentError):
    """Error raised when an experiment cannot be found."""


class AnalysisResultNotFoundError(ExperimentError):
    """Error raised when an analysis result cannot be found."""


class PlotNotFoundError(ExperimentError):
    """Error raised when a plot cannot be found."""
