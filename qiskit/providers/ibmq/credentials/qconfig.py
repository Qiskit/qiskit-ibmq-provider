# -*- coding: utf-8 -*-

# This code is part of Qiskit.
#
# (C) Copyright IBM 2017, 2018.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Utilities for reading credentials from the deprecated `Qconfig.py` file."""

import os
from collections import OrderedDict
from importlib.util import module_from_spec, spec_from_file_location

from .credentials import Credentials
from .exceptions import CredentialsError

DEFAULT_QCONFIG_FILE = 'Qconfig.py'
QE_URL = 'https://quantumexperience.ng.bluemix.net/api'


def read_credentials_from_qconfig():
    """Read a `QConfig.py` file and return its credentials.

    Returns:
        dict: dictionary with the credentials, in the form::

            {credentials_unique_id: Credentials}

    Raises:
        CredentialsError: if the Qconfig.py was not parseable. Please note that
            this exception is not raised if the file does not exist (instead, an
            empty dict is returned).
    """
    if not os.path.isfile(DEFAULT_QCONFIG_FILE):
        return OrderedDict()
    else:
        # Note this is nested inside the else to prevent some tools marking
        # the whole method as deprecated.
        pass
        # TODO: reintroduce when we decide on deprecating
        # warnings.warn(
        #     "Using 'Qconfig.py' for storing the credentials will be deprecated in"
        #     "upcoming versions (>0.6.0). Using .qiskitrc is recommended",
        #     DeprecationWarning)

    try:
        spec = spec_from_file_location('Qconfig', DEFAULT_QCONFIG_FILE)
        q_config = module_from_spec(spec)
        spec.loader.exec_module(q_config)

        if hasattr(q_config, 'config'):
            credentials = q_config.config.copy()
        else:
            credentials = {}
        credentials['token'] = q_config.APItoken
        credentials['url'] = credentials.get('url', QE_URL)
    except Exception as ex:  # pylint: disable=broad-except
        raise CredentialsError('Error loading Qconfig.py: %s' % str(ex))

    credentials = Credentials(**credentials)
    return OrderedDict({credentials.unique_id(): credentials})
