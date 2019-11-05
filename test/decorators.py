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

import os
from functools import wraps
from unittest import SkipTest

from qiskit.test.testing_options import get_test_options
from qiskit.providers.ibmq import least_busy
from qiskit.providers.ibmq.ibmqfactory import IBMQFactory
from qiskit.providers.ibmq.credentials import (Credentials,
                                               discover_credentials)


def requires_qe_access(func):
    """Decorator that signals that the test uses the online API.

    It involves:
        * determines if the test should be skipped by checking environment
            variables.
        * if the `USE_ALTERNATE_ENV_CREDENTIALS` environment variable is
          set, it reads the credentials from an alternative set of environment
          variables.
        * if the test is not skipped, it reads `qe_token` and `qe_url` from
            `Qconfig.py`, environment variables or qiskitrc.
        * if the test is not skipped, it appends `qe_token` and `qe_url` as
            arguments to the test function.

    Args:
        func (callable): test function to be decorated.

    Returns:
        callable: the decorated function.
    """
    @wraps(func)
    def _wrapper(obj, *args, **kwargs):
        if get_test_options()['skip_online']:
            raise SkipTest('Skipping online tests')

        credentials = _get_credentials()
        obj.using_ibmq_credentials = credentials.is_ibmq()
        kwargs.update({'qe_token': credentials.token,
                       'qe_url': credentials.url})

        return func(obj, *args, **kwargs)

    return _wrapper


def requires_provider(func):
    """Decorator that signals the test uses the online API, via a provider.

    This decorator delegates into the `requires_qe_access` decorator, but
    instead of the credentials it appends a `provider` argument to the decorated
    function.

    Args:
        func (callable): test function to be decorated.

    Returns:
        callable: the decorated function.
    """
    @wraps(func)
    @requires_qe_access
    def _wrapper(*args, **kwargs):
        ibmq_factory = IBMQFactory()
        qe_token = kwargs.pop('qe_token')
        qe_url = kwargs.pop('qe_url')
        provider = ibmq_factory.enable_account(qe_token, qe_url)
        kwargs.update({'provider': provider})

        return func(*args, **kwargs)

    return _wrapper


def requires_device(func):
    """Decorator that retrieves the appropriate backend to use for testing.

    This decorator delegates into the `requires_provider` decorator, but instead of the
    provider it appends a `backend` argument to the decorated function.

    It involves:
        * If the `QE_DEVICE` environment variable is set, the test is to be
            run against the backend specified by `QE_DEVICE`.
        * If the `QE_DEVICE` environment variable is not set, the test is to
            be run against least busy device.

    Args:
        func (callable): test function to be decorated.

    Returns:
        callable: the decorated function.
    """
    @wraps(func)
    @requires_provider
    def _wrapper(*args, **kwargs):
        provider = kwargs.pop('provider')

        _backend = None
        if os.getenv('QE_DEVICE'):
            backend_name = os.getenv('QE_DEVICE')
            _backend = provider.get_backend(backend_name)
        else:
            _backend = least_busy(provider.backends(simulator=False))

        kwargs.update({'backend': _backend})

        return func(*args, **kwargs)

    return _wrapper


def run_on_device(func):
    """Decorator that signals that the test should run on a real or semi-real device.

    It involves:
        * skips the test if online tests are to be skipped.
        * if the `USE_STAGING_CREDENTIALS` environment variable is set, then enable
            the staging account using credentials specified by the
            `QE_STAGING_TOKEN` and `QE_STAGING_URL` environment variables.
            Backend name specified by `QE_STAGING_DEVICE`, if set, will
            also be used.
        * else skips the test if slow tests are to be skipped.
        * else enable the account using credentials returned by `_get_credentials()`
            and use the backend specified by `QE_DEVICE`, if set.
        * if backend value is not already set, use the least busy backend.
        * appends arguments `provider` and `backend` to the decorated function.

    Args:
        func (callable): test function to be decorated.

    Returns:
        callable: the decorated function.
    """
    @wraps(func)
    def _wrapper(obj, *args, **kwargs):

        if get_test_options()['skip_online']:
            raise SkipTest('Skipping online tests')

        if os.getenv('USE_STAGING_CREDENTIALS', ''):
            credentials = Credentials(os.getenv('QE_STAGING_TOKEN'), os.getenv('QE_STAGING_URL'))
            backend_name = os.getenv('QE_STAGING_DEVICE', None)
        else:
            if not get_test_options()['run_slow']:
                raise SkipTest('Skipping slow tests')
            credentials = _get_credentials()
            backend_name = os.getenv('QE_DEVICE', None)

        obj.using_ibmq_credentials = credentials.is_ibmq()
        ibmq_factory = IBMQFactory()
        provider = ibmq_factory.enable_account(credentials.token, credentials.url)
        kwargs.update({'provider': provider})
        _backend = provider.get_backend(backend_name) if backend_name else \
            least_busy(provider.backends(simulator=False))
        kwargs.update({'backend': _backend})

        return func(obj, *args, **kwargs)

    return _wrapper


def _get_credentials():
    """Finds the credentials for a specific test and options.

    Returns:
        Credentials: set of credentials

    Raises:
        Exception: when the credential could not be set and they are needed
            for that set of options
    """
    if os.getenv('USE_ALTERNATE_ENV_CREDENTIALS', ''):
        # Special case: instead of using the standard credentials mechanism,
        # load them from different environment variables. This assumes they
        # will always be in place, as is used by the Travis setup.
        return Credentials(os.getenv('IBMQ_TOKEN'), os.getenv('IBMQ_URL'))

    # Attempt to read the standard credentials.
    discovered_credentials = discover_credentials()

    if discovered_credentials:
        # Decide which credentials to use for testing.
        if len(discovered_credentials) > 1:
            try:
                # Attempt to use QE credentials.
                return discovered_credentials[(None, None, None)]
            except KeyError:
                pass

        # Use the first available credentials.
        return list(discovered_credentials.values())[0]

    raise Exception('Could not locate valid credentials.') from None
