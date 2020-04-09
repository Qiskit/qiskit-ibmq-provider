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

"""Helper for updating IBM Quantum Experience credentials from v1 to v2."""

from typing import Optional
from .credentials import Credentials
from .configrc import (read_credentials_from_qiskitrc,
                       remove_credentials,
                       store_credentials)


QE_URL = 'https://quantumexperience.ng.bluemix.net/api'
QCONSOLE_URL = 'https://q-console-api.mybluemix.net/api'

QE2_URL = 'https://api.quantum-computing.ibm.com/api'
QCONSOLE2_URL = 'https://api-qcon.quantum-computing.ibm.com/api'

QE2_AUTH_URL = 'https://auth.quantum-computing.ibm.com/api'


def update_credentials(force: bool = False) -> Optional[Credentials]:
    """Update or provide information about updating stored credentials.

    This function is an interactive helper to update credentials stored in
    disk from IBM Quantum Experience v1 to v2. Upon invocation, the
    function will inspect the credentials stored in disk and attempt to
    convert them to the new version, displaying the changes and asking for
    confirmation before overwriting the credentials.

    Args:
        force: If ``True``, disable interactive prompts and perform the
            changes.

    Returns:
        IBM Quantum Experience v2 credentials, if it was possible to make the
        update. Otherwise ``None``.
    """
    # Get the list of stored credentials.
    stored_credentials, _ = read_credentials_from_qiskitrc()
    credentials_list = list(stored_credentials.values())

    new_credentials = []
    hub_lines = []
    warnings = []
    provider_number = 1

    # Parse the credentials found.
    for credentials in credentials_list:
        if is_directly_updatable(credentials):
            # Credentials can be updated to the new URL directly.
            new_credentials.append(Credentials(credentials.token, QE2_AUTH_URL,
                                               proxies=credentials.proxies,
                                               verify=credentials.verify))
        else:
            if credentials.url == QE2_AUTH_URL:
                # Credential is already for auth url.
                warnings.append('The stored account with url "{}" is already '
                                'an IBM Q Experience v2 account.'.format(credentials.url))
            elif credentials.is_ibmq():
                new_credentials.append(Credentials(credentials.token,
                                                   QE2_AUTH_URL,
                                                   proxies=credentials.proxies,
                                                   verify=credentials.verify))
                hub_lines.append(
                    "  provider{} = IBMQ.get_provider(hub='{}', group='{}', "
                    "project='{}')".format(provider_number,
                                           credentials.hub,
                                           credentials.group,
                                           credentials.project))
                provider_number += 1
            else:
                # Unknown URL - do not act on it.
                warnings.append('The stored account with url "{}" could not be '
                                'parsed.'.format(credentials.url))

    # Check that the conversion can be performed.
    print('Found {} credentials.'.format(len(credentials_list)))

    if not new_credentials:
        print('No credentials available for updating could be found. No '
              'action will be performed.')
        if warnings:
            print('Warnings:')
            print('\n'.join(warnings))

        return None

    # Check if any of the meaningful fields differ.
    final_credentials = new_credentials[0]
    tuples = [(credentials.token, credentials.proxies, credentials.verify)
              for credentials in new_credentials]

    if not all(field_tuple == tuples[0] for field_tuple in tuples):
        warnings.append('Multiple credentials found with different settings. The '
                        'conversion will use the settings from the first '
                        'IBM Q Experience v1 account found.')

    # Print a summary of the changes.
    print('The credentials stored will be replaced with a single entry with '
          'token "{}" and the new IBM Q Experience v2 URL ({}).'.format(
              final_credentials.token, QE2_AUTH_URL))
    if final_credentials.proxies:
        print('The existing proxy configuration will be preserved.')

    if warnings:
        print('\nWarnings:')
        print('\n'.join(warnings))

    print('\nIn order to access the provider, please use the new '
          '"IBMQ.get_provider()" methods:')
    print('\n  provider0 = IBMQ.load_account()')
    if hub_lines:
        print('\n'.join(hub_lines))
    print('\nNote you need to update your programs in order to retrieve '
          'backends from a specific provider directly:')
    print('\n  backends = provider0.backends()')
    print("  backend = provider0.get_backend('ibmq_qasm_simulator')")

    # Ask for confirmation from the user.
    if not force:
        confirmation = input('\nUpdate the credentials? [y/N]: ')
        if confirmation not in ('y', 'Y'):
            return None

    # Proceed with overwriting the credentials.
    for credentials in credentials_list:
        remove_credentials(credentials)
    store_credentials(final_credentials)

    return final_credentials


def is_directly_updatable(credentials: Credentials) -> bool:
    """Returns ``True`` if credentials can be updated directly."""
    if credentials.base_url == QE_URL:
        return True

    if credentials.base_url in (QCONSOLE_URL, QE2_URL, QCONSOLE2_URL):
        if credentials.base_url == credentials.url:
            return True

    return False
