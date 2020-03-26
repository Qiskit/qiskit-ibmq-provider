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

"""Exceptions related to the visualization modules."""

from ..exceptions import IBMQError


class VisualizationError(IBMQError):
    """Base class for errors raised by the visualization modules."""
    pass


class VisualizationValueError(VisualizationError, ValueError):
    """Value errors raised by the visualization modules."""
    pass


class VisualizationTypeError(VisualizationError, TypeError):
    """Type errors raised by the visualization modules."""
    pass
