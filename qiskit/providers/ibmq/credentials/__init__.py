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

"""Utilities for working with credentials for the IBMQ package."""

from collections import OrderedDict
from typing import Dict, Optional
import logging

from .credentials import Credentials, HubGroupProject
from .exceptions import CredentialsError
from .configrc import read_credentials_from_qiskitrc, store_credentials
from .environ import read_credentials_from_environ
from .qconfig import read_credentials_from_qconfig

logger = logging.getLogger(__name__)


def discover_credentials(
        qiskitrc_filename: Optional[str] = None
) -> Dict[HubGroupProject, Credentials]:
    """Automatically discover credentials for IBM Q.

    This method looks for credentials in the following locations, in order,
    and returning as soon as credentials are found::

        1. in the `Qconfig.py` file in the current working directory.
        2. in the environment variables.
        3. in the `qiskitrc` configuration file

    Args:
        qiskitrc_filename: location for the `qiskitrc` configuration
            file. If `None`, defaults to `{HOME}/.qiskitrc/qiskitrc`.

    Returns:
        dictionary with the contents of the configuration file, with
            the form::

            {credentials_unique_id: Credentials}
    """
    credentials = OrderedDict()  # type: ignore[var-annotated]

    # dict[str:function] that defines the different locations for looking for
    # credentials, and their precedence order.
    readers = OrderedDict([
        ('qconfig', (read_credentials_from_qconfig, {})),
        ('environment variables', (read_credentials_from_environ, {})),
        ('qiskitrc', (read_credentials_from_qiskitrc,
                      {'filename': qiskitrc_filename}))
    ])

    # Attempt to read the credentials from the different sources.
    for display_name, (reader_function, kwargs) in readers.items():
        try:
            credentials = reader_function(**kwargs)  # type: ignore[arg-type]
            logger.info('Using credentials from %s', display_name)
            if credentials:
                break
        except CredentialsError as ex:
            logger.warning(
                'Automatic discovery of %s credentials failed: %s',
                display_name, str(ex))

    return credentials
