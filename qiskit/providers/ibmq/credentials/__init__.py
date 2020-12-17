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
from typing import Dict, Optional, Tuple, Any
import logging

from .credentials import Credentials
from .hubgroupproject import HubGroupProject
from .exceptions import (CredentialsError, InvalidCredentialsFormatError,
                         CredentialsNotFoundError, HubGroupProjectInvalidStateError)
from .configrc import read_credentials_from_qiskitrc, store_credentials
from .environ import read_credentials_from_environ

logger = logging.getLogger(__name__)


def discover_credentials(
        qiskitrc_filename: Optional[str] = None
) -> Tuple[Dict[HubGroupProject, Credentials], HubGroupProject]:
    """Automatically discover credentials for IBM Quantum Experience.

    This method looks for credentials in the following places in order and
    returns the first ones found:

        1. The the environment variables.
        2. The ``qiskitrc`` configuration file

    Args:
        qiskitrc_filename: Full path to the ``qiskitrc`` configuration
            file. If ``None``, ``$HOME/.qiskitrc/qiskitrc`` is used.

    Raises:
        HubGroupProjectInvalidStateError: If the default provider stored on
            disk could not be parsed.

    Returns:
        A tuple containing the found credentials, if any, and the default
        provider stored, if specified in the configuration file. The format
        for the found credentials is ``{credentials_unique_id: Credentials}``,
        whereas the default provider is represented as a `HubGroupProject` instance.
    """
    credentials = OrderedDict()  # type: OrderedDict[HubGroupProject, Credentials]

    # dict[str:function] that defines the different locations for looking for
    # credentials, and their precedence order.
    readers = OrderedDict([
        ('environment variables', (read_credentials_from_environ, {})),
        ('qiskitrc', (read_credentials_from_qiskitrc,
                      {'filename': qiskitrc_filename}))
    ])  # type: OrderedDict[str, Any]

    # The default provider stored in the `qiskitrc` file.
    stored_provider_hgp = None
    # Attempt to read the credentials from the different sources.
    for display_name, (reader_function, kwargs) in readers.items():
        try:
            stored_account_info = reader_function(**kwargs)  # type: ignore[arg-type]
            if display_name == 'qiskitrc':
                # Read from `qiskitrc`, which may have a stored provider.
                credentials, stored_provider_hgp = stored_account_info
            else:
                credentials = stored_account_info
            if credentials:
                logger.info('Using credentials from %s', display_name)
                break
        except CredentialsError as ex:
            logger.warning(
                'Automatic discovery of %s credentials failed: %s',
                display_name, str(ex))

    return credentials, stored_provider_hgp
