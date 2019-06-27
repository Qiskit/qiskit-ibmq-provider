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

"""Helper for updating credentials from API 1 to API 2."""

from .credentials import Credentials
from .configrc import read_credentials_from_qiskitrc


QE_URL = 'https://quantumexperience.ng.bluemix.net/api'
QCONSOLE_URL = 'https://q-console-api.mybluemix.net/api'

QE2_URL = 'https://api.quantum-computing.ibm.com/api'
QCONSOLE2_URL = 'https://api-qcon.quantum-computing.ibm.com/api'

QE2_AUTH_URL = 'https://auth.quantum-computing.ibm.com/api'


def update_credentials(force=False):
    """Update or provide information about updating stored credentials.

    Args:
        force (bool): if `True`, disable interactive prompts and perform the
            changes.
    """
    # Get the list of stored credentials.
    credentials_list = list(read_credentials_from_qiskitrc().values())

    new_credentials = []
    hub_lines = []
    warnings = []
    provider_number = 1
    first_converted_url = None

    # Parse the credentials found.
    for credentials in credentials_list:
        if is_directly_updatable(credentials):
            new_credentials.append(Credentials(credentials.token, QE2_AUTH_URL,
                                               proxies=credentials.proxies,
                                               verify=credentials.verify))
            if not first_converted_url:
                first_converted_url = credentials.url
        else:
            if credentials.is_ibmq():
                new_credentials.append(Credentials(credentials.token,
                                                   QE2_AUTH_URL,
                                                   proxies=credentials.proxies,
                                                   verify=credentials.verify))
                if not first_converted_url:
                    first_converted_url = credentials.url

                hub_lines.append(
                    "provider{} = IBMQ.get_provider(hub='{}', group='{}',"
                    "project='{})".format(provider_number,
                                          credentials.hub,
                                          credentials.group,
                                          credentials.project))
                provider_number += 1
            else:
                # Unknown URL - do not act on it.
                warnings.append('The stored account with url "{}" could not be '
                                'parsed and will be discarded.')

    # Check if any of the meaningful fields differ.
    tuples = [(credentials.token, credentials.proxies, credentials.verify)
              for credentials in new_credentials]

    if not all(field_tuple==tuples[0] for field_tuple in tuples):
        warnings.append("The credentials stored differ in several fields. The "
                        "conversion will use the settings previously stored "
                        "for the v1 account at '{}'.".format(first_converted_url))

    return credentials_list


def is_directly_updatable(credentials):
    """Returns `True` if credentials can be updated directly."""
    if credentials.base_url in (QE_URL, QE2_AUTH_URL):
        return True

    if credentials.base_url in (QCONSOLE_URL, QE2_URL, QCONSOLE2_URL):
        if credentials.base_url == credentials.url:
            return True

    return False
