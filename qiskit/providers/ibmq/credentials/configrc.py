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

"""Utilities for reading and writing credentials from and to configuration files."""

import logging
import os
from ast import literal_eval
from collections import OrderedDict
from configparser import ConfigParser, ParsingError
from typing import Dict, Tuple, Optional, Any

from .credentials import Credentials
from .hubgroupproject import HubGroupProject
from .exceptions import InvalidCredentialsFormatError, CredentialsNotFoundError

logger = logging.getLogger(__name__)

DEFAULT_QISKITRC_FILE = os.path.join(os.path.expanduser("~"),
                                     '.qiskit', 'qiskitrc')
"""Default location of the configuration file."""


def to_bool(val: str) -> bool:
    """converts val to boolean obj.
    Note: bool(x) always returns true.

    Args:
        val: a string val

    Returns:
        the converted boolean
    """
    return val.lower() == 'true'


ACTIVE_PREFERENCES = {
    'experiment': [('auto_save', to_bool)]
}


def read_credentials_from_qiskitrc(
        filename: Optional[str] = None
) -> Tuple[Dict[HubGroupProject, Credentials], HubGroupProject]:
    """Read a configuration file and return a dictionary with its contents.

    Args:
        filename: Full path to the configuration file. If ``None``, the default
            location is used (``$HOME/.qiskit/qiskitrc``).

    Returns:
        A tuple containing the found credentials, if any, and the default
        provider stored, if specified in the configuration file. The format
        for the found credentials is ``{credentials_unique_id: Credentials}``,
        whereas the default provider is represented as a `HubGroupProject` instance.

    Raises:
        InvalidCredentialsFormatError: If the file cannot be parsed. Note
            that this exception is not raised if the input file
            does not exist, and an empty dictionary is returned instead.
        HubGroupProjectInvalidStateError: If the default provider stored on
            disk could not be parsed.
    """
    filename = filename or DEFAULT_QISKITRC_FILE
    config_parser = ConfigParser()
    try:
        config_parser.read(filename)
    except ParsingError as ex:
        raise InvalidCredentialsFormatError(
            'Error parsing file {}: {}'.format(filename, str(ex))) from ex

    # Build the credentials dictionary.
    credentials_dict = OrderedDict()  # type: ignore[var-annotated]
    default_provider_hgp = None

    for name in config_parser.sections():
        if name.startswith('ibmq'):
            single_credentials = dict(config_parser.items(name))
            # Individually convert keys to their right types.
            # TODO: consider generalizing, moving to json configuration or a more
            # robust alternative.
            if 'proxies' in single_credentials.keys():
                single_credentials['proxies'] = literal_eval(
                    single_credentials['proxies'])
            if 'verify' in single_credentials.keys():
                single_credentials['verify'] = bool(  # type: ignore[assignment]
                    single_credentials['verify'])
            if 'default_provider' in single_credentials.keys():
                default_provider_hgp = HubGroupProject.from_stored_format(
                    single_credentials['default_provider'])

                # Delete `default_provider`, since it's not used by the `Credentials` constructor.
                del single_credentials['default_provider']

            # Retrieve locally-stored preferences
            # Criteria: It is (1) an active pref and (2) a value was found for it
            # WARNING: This kind of linear storage in the .qiskitrc becomes dangerous
            #  when we have nested prefs (if conflicting names). Storage should move to JSON.
            preferences: Dict[str, Dict] = {}
            # pylint: disable=consider-iterating-dictionary
            for category in ACTIVE_PREFERENCES.keys():
                for opt, opt_type in ACTIVE_PREFERENCES[category]:
                    if opt in single_credentials.keys():
                        if not preferences.get(category):
                            preferences[category] = {}
                        preferences[category][opt] = opt_type(  # type: ignore[assignment]
                            single_credentials[opt])
                        del single_credentials[opt]
            new_credentials = Credentials(preferences=preferences,
                                          **single_credentials)  # type: ignore[arg-type]

            credentials_dict[new_credentials.unique_id()] = new_credentials

    return credentials_dict, default_provider_hgp


def write_qiskit_rc(
        credentials: Dict[HubGroupProject, Credentials],
        default_provider: Optional[HubGroupProject] = None,
        filename: Optional[str] = None
) -> None:
    """Write credentials to the configuration file.

    Args:
        credentials: Dictionary with the credentials, in the
            ``{credentials_unique_id: Credentials}`` format.
        default_provider: If specified, the provider to store in the configuration
            file, represented as a ``HubGroupProject`` instance.
        filename: Full path to the configuration file. If ``None``, the default
            location is used (``$HOME/.qiskit/qiskitrc``).
    """
    def _credentials_object_to_dict(
            credentials_obj: Credentials,
            default_provider_to_store: Optional[HubGroupProject]
    ) -> Dict[str, Any]:
        """Convert a ``Credential`` object to a dictionary."""
        credentials_dict = {key: getattr(credentials_obj, key) for key in
                            ['token', 'url', 'proxies', 'verify']
                            if getattr(credentials_obj, key)}

        # Handle `Credential.preferences` (i.e add valid prefs to dict)
        active_pref_names = []
        for category in ACTIVE_PREFERENCES.keys():  # pylint: disable=consider-iterating-dictionary
            for name, _ in ACTIVE_PREFERENCES[category]:
                active_pref_names.append(name)

        for category in credentials_obj.preferences.keys():
            for name, val in credentials_obj.preferences[category].items():
                # If pref is a valid, active experiment pref,
                # Add it directly to the credential dictionary
                if name in active_pref_names:
                    credentials_dict[name] = val

        # Save the default provider to disk, if specified.
        if default_provider_to_store:
            credentials_dict['default_provider'] = default_provider_to_store.to_stored_format()

        return credentials_dict

    def _section_name(credentials_: Credentials) -> str:
        """Return a string suitable for use as a unique section name."""
        base_name = 'ibmq'
        if credentials_.is_ibmq():
            base_name = '{}_{}_{}_{}'.format(base_name,
                                             *credentials_.unique_id().to_tuple())
        return base_name

    filename = filename or DEFAULT_QISKITRC_FILE
    # Create the directories and the file if not found.
    os.makedirs(os.path.dirname(filename), exist_ok=True)

    unrolled_credentials = {
        _section_name(credentials_object):
            _credentials_object_to_dict(credentials_object, default_provider)
        for _, credentials_object in credentials.items()
    }

    # Write the configuration file.
    with open(filename, 'w') as config_file:
        config_parser = ConfigParser()
        config_parser.read_dict(unrolled_credentials)
        config_parser.write(config_file)


def store_credentials(
        credentials: Credentials,
        default_provider: Optional[HubGroupProject] = None,
        overwrite: bool = False,
        filename: Optional[str] = None
) -> None:
    """Store the credentials for a single account in the configuration file.

    Args:
        credentials: Credentials to save.
        default_provider: If specified, the provider to store in the configuration
            file, represented as a ``HubGroupProject`` instance.
        overwrite: ``True`` if any existing credentials are to be overwritten.
        filename: Full path to the configuration file. If ``None``, the default
            location is used (``$HOME/.qiskit/qiskitrc``).
    """
    # Read the current providers stored in the configuration file.
    filename = filename or DEFAULT_QISKITRC_FILE
    stored_credentials, _ = read_credentials_from_qiskitrc(filename)

    # Check if duplicated credentials are already stored. By convention,
    # we assume (hub, group, project) is always unique.
    if credentials.unique_id() in stored_credentials and not overwrite:
        logger.warning('Credentials already present. '
                       'Set overwrite=True to overwrite.')
        return

    # Append and write the credentials to file.
    stored_credentials[credentials.unique_id()] = credentials
    write_qiskit_rc(stored_credentials, default_provider, filename)


def remove_credentials(
        credentials: Credentials,
        filename: Optional[str] = None
) -> None:
    """Remove credentials from the configuration file.

    Args:
        credentials: Credentials to remove.
        filename: Full path to the configuration file. If ``None``, the default
            location is used (``$HOME/.qiskit/qiskitrc``).

    Raises:
        CredentialsNotFoundError: If there is no account with that name on the
            configuration file.
    """
    # Set the name of the Provider from the class.
    stored_credentials, _ = read_credentials_from_qiskitrc(filename)

    try:
        del stored_credentials[credentials.unique_id()]
    except KeyError:
        raise CredentialsNotFoundError('The account {} does not exist in the configuration file.'
                                       .format(credentials.unique_id())) from None
    write_qiskit_rc(stored_credentials, filename)
