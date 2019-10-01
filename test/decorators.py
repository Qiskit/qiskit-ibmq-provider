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
from qiskit.providers.ibmq.ibmqfactory import IBMQFactory
from qiskit.providers.ibmq.credentials import (Credentials,
                                               discover_credentials)
from qiskit.providers.ibmq.exceptions import IBMQAccountError


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


def run_on_staging(func):
    """Decorator that signals that the test runs on the staging system.

    It involves:
        * reads the `QE_STG_TOKEN`, `QE_STG_URL`, and `QE_STG_HUB` environment
            variables.
        * if all variables are set, then their values are used as the
            credentials; otherwise the test is skipped.
        * if the test is not skipped, enables the staging account and
            appends it as the `provider` argument to the test function.

    Args:
        func (callable): test function to be decorated.

    Returns:
        callable: the decorated function.
    """
    @wraps(func)
    def _wrapper(obj, *args, **kwargs):
        stg_token = os.getenv('QE_STG_TOKEN')
        stg_url = os.getenv('QE_STG_URL')
        stg_hub = os.getenv('QE_STG_HUB')
        if not (stg_token and stg_url and stg_hub):
            raise SkipTest('Skipping staging tests')

        credentials = Credentials(stg_token, stg_url)
        obj.using_ibmq_credentials = credentials.is_ibmq()
        ibmq_factory = IBMQFactory()

        try:
            # Disable account in case one is already in use
            ibmq_factory.disable_account()
        except IBMQAccountError:
            pass

        ibmq_factory.enable_account(credentials.token, credentials.url)
        provider = ibmq_factory.get_provider(hub=stg_hub)
        kwargs.update({'provider': provider})

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
