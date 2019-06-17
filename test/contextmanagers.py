# -*- coding: utf-8 -*-

# This code is part of Qiskit.
#
# (C) Copyright IBM 2019.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Context managers for using with IBMQProvider unit tests."""

import os
from contextlib import contextmanager


@contextmanager
def custom_envs(new_environ):
    """Context manager that modifies environment variables.

    Args:
        new_environ (dict): a dictionary of modified environment variables.
    """
    # Remove the original variables from `os.environ`.
    # Store the original `os.environ`.
    os_environ_original = os.environ.copy()
    modified_environ = {**os.environ, **new_environ}
    try:
        os.environ = modified_environ
        yield
    finally:
        # Restore the original `os.environ`.
        os.environ = os_environ_original


@contextmanager
def no_envs(vars_to_remove):
    """Context manager that disables environment variables.

    Args:
        vars_to_remove (list): environment variables to remove.

    """
    # Remove the original variables from `os.environ`.
    # Store the original `os.environ`.
    os_environ_original = os.environ.copy()
    modified_environ = {key: value for key, value in os.environ.items()
                        if key not in vars_to_remove}
    try:
        os.environ = modified_environ
        yield
    finally:
        # Restore the original `os.environ`.
        os.environ = os_environ_original
