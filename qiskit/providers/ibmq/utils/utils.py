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

"""General utility functions."""

import re
import keyword
from functools import wraps
from typing import Callable, Any
from inspect import getfullargspec, signature


def to_python_identifier(name: str) -> str:
    """Convert a name to a valid Python identifier.

    Args:
        name: Name to be converted.

    Returns:
        Name that is a valid Python identifier.
    """
    # Python identifiers can only contain alphanumeric characters
    # and underscores and cannot start with a digit.
    pattern = re.compile(r"\W|^(?=\d)", re.ASCII)
    if not name.isidentifier():
        name = re.sub(pattern, '_', name)

    # Convert to snake case
    name = re.sub('((?<=[a-z0-9])[A-Z]|(?!^)(?<!_)[A-Z](?=[a-z]))', r'_\1', name).lower()

    while keyword.iskeyword(name):
        name += '_'

    return name


def require_signature_compatibility(func_to_compare: Callable) -> Callable:
    """Decorator that ensures the decorated function's signature is compatible with
    the signature of the function passed as argument.

    Note:
        The decorated function's signature is compatible with the signature of the
        function passed as argument if and only if all the parameters of the decorated
        function are within the parameter list of the function passed as argument.

    Args:
        func_to_compare: function to compare compatibility against.

    Returns:
    """

    def inner_function(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*_args: Any, **_kwargs: Any) -> Any:
            func_args = getattr(getfullargspec(func), 'args', [])
            func_to_compare_args = getattr(getfullargspec(func_to_compare), 'args', [])

            # Ensure all the decorated function's parameters are compatible with
            # the parameters of the function passed as argument.
            if not all(arg in func_to_compare_args for arg in func_args):
                func_name = getattr(func, '__qualname__', str(func))
                func_to_compare_name = getattr(func_to_compare, '__qualname__', str(func_to_compare))
                differing_args = set(func_args) - set(func_to_compare_args)

                raise Exception("`{}` does not match the parameters of `{}`. "
                                "`{}` has the extra parameter(s): {}"
                                .format(func_name, func_to_compare_name, func_name, differing_args))

            return func(*_args, **_kwargs)
        return wrapper

    return inner_function
