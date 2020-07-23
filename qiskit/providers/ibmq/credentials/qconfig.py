# -*- coding: utf-8 -*-

# This code is part of Qiskit.
#
# (C) Copyright IBM 2017, 2019.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Utilities for reading credentials from the deprecated ``Qconfig.py`` file."""

import os
import warnings
from collections import OrderedDict
from typing import Dict
from importlib.util import module_from_spec, spec_from_file_location

from .credentials import Credentials
from .hubgroupproject import HubGroupProject
from .exceptions import InvalidCredentialsFormatError

DEFAULT_QCONFIG_FILE = 'Qconfig.py'
QE_URL = 'https://quantumexperience.ng.bluemix.net/api'


def read_credentials_from_qconfig() -> Dict[HubGroupProject, Credentials]:
    """Read the ``QConfig.py`` file and return its credentials.

    Returns:
        A dictionary with the read credentials, in the
        ``{credentials_unique_id: Credentials}`` format.

    Raises:
        InvalidCredentialsFormatError: If the ``Qconfig.py`` file could not
            be parsed. Note that this exception is not raised if the input file
            does not exist, and an empty dictionary is returned instead.
    """
    if not os.path.isfile(DEFAULT_QCONFIG_FILE):
        return OrderedDict()
    else:
        # TODO: remove in 0.9.
        warnings.warn(
            "Using 'Qconfig.py' for storing credentials is deprecated and will "
            "be removed in the next release. Please use .qiskitrc instead.",
            category=DeprecationWarning, stacklevel=4)

    try:
        spec = spec_from_file_location('Qconfig', DEFAULT_QCONFIG_FILE)
        q_config = module_from_spec(spec)
        spec.loader.exec_module(q_config)  # type: ignore[attr-defined]

        if hasattr(q_config, 'config'):
            credentials = q_config.config.copy()  # type: ignore[attr-defined]
        else:
            credentials = {}
        credentials['token'] = q_config.APItoken    # type: ignore[attr-defined]
        credentials['url'] = credentials.get('url', QE_URL)
    except Exception as ex:  # pylint: disable=broad-except
        raise InvalidCredentialsFormatError(
            'Error loading Qconfig.py: {}'.format(str(ex))) from ex

    credentials = Credentials(**credentials)
    return OrderedDict({credentials.unique_id(): credentials})
