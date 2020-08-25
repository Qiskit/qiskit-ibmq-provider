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

"""Utilities for working with IBM Quantum Experience experiments."""

from functools import wraps

from .exceptions import ExperimentError


def requires_experiment_uuid(func):
    """Decorator that signals that the function requires an experiment UUID.

    Args:
        func (callable): test function to be decorated.

    Returns:
        callable: the decorated function.
    """
    @wraps(func)
    def _wrapper(experiment, *args, **kwargs):
        if not experiment.uuid:
            raise ExperimentError(
                "{} requires the UUID of this experiment to be known.".format(func.__name__))
        return func(experiment, *args, **kwargs)

    return _wrapper
