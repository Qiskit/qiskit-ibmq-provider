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

"""
======================================================
Credentials (:mod:`qiskit.providers.ibmq.credentials`)
======================================================

.. currentmodule:: qiskit.providers.ibmq.credentials

Utilities for working with IBM Quantum Experience account credentials.

Classes
=========

.. autosummary::
    :toctree: ../stubs/

    Credentials

Exceptions
==========
.. autosummary::
    :toctree: ../stubs/

    CredentialsError
    InvalidCredentialsFormatError
    CredentialsNotFoundError
"""

from collections import OrderedDict
from typing import Dict, Optional
import logging

from .credentials import Credentials, HubGroupProject
from .exceptions import CredentialsError, InvalidCredentialsFormatError, CredentialsNotFoundError
from .configrc import read_credentials_from_qiskitrc, store_credentials
from .environ import read_credentials_from_environ
from .qconfig import read_credentials_from_qconfig

logger = logging.getLogger(__name__)


def discover_credentials(
        qiskitrc_filename: Optional[str] = None
) -> Dict[HubGroupProject, Credentials]:
    """Automatically discover credentials for IBM Quantum Experience.

    This method looks for credentials in the following places in order and
    returns the first ones found:

        1. The ``Qconfig.py`` file in the current working directory.
        2. The the environment variables.
        3. The ``qiskitrc`` configuration file

    Args:
        qiskitrc_filename: Full path to the ``qiskitrc`` configuration
            file. If ``None``, ``$HOME/.qiskitrc/qiskitrc`` is used.

    Returns:
        A dictionary of found credentials, if any, in the
        ``{credentials_unique_id: Credentials}`` format.
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
