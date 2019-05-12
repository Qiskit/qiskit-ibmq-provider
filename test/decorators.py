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

"""Decorators for using with IBMQProvider unit tests."""

from functools import wraps
from unittest import SkipTest


def requires_new_api_auth_credentials(func):
    """Decorator that signals that the test requires new API auth credentials.

    Note: this decorator is meant to be used *after* ``requires_qe_access``, as
    it depends on the ``qe_url`` parameter.

    Args:
        func (callable): test function to be decorated.

    Returns:
        callable: the decorated function.

    Raises:
        SkipTest: if no new API auth credentials were found.
    """
    @wraps(func)
    def _wrapper(self, *args, **kwargs):
        qe_url = kwargs.get('qe_url')
        # TODO: provide a way to check it in a more robust way.
        if not ('quantum-computing.ibm.com/api' in qe_url and
                'auth' in qe_url):
            raise SkipTest(
                'Skipping test that requires new API auth credentials')

        return func(self, *args, **kwargs)

    return _wrapper


def requires_classic_api_credentials(func):
    """Decorator that signals that the test requires classic API credentials.

    Note: this decorator is meant to be used *after* ``requires_qe_access``, as
    it depends on the ``qe_url`` parameter.

    Args:
        func (callable): test function to be decorated.

    Returns:
        callable: the decorated function.

    Raises:
        SkipTest: if no classic API credentials were found.
    """
    @wraps(func)
    def _wrapper(self, *args, **kwargs):
        qe_url = kwargs.get('qe_url')
        # TODO: provide a way to check it in a more robust way.
        if 'quantum-computing.ibm.com/api' in qe_url:
            raise SkipTest(
                'Skipping test that requires new API auth credentials')

        return func(self, *args, **kwargs)

    return _wrapper
