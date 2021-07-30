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
from collections import defaultdict
from configparser import ConfigParser, ParsingError
from typing import Dict, Tuple, Optional, Any, Union

from .credentials import Credentials
from .hubgroupproject import HubGroupProject
from .exceptions import InvalidCredentialsFormatError, CredentialsNotFoundError

logger = logging.getLogger(__name__)

DEFAULT_QISKITRC_FILE = os.path.join(os.path.expanduser("~"),
                                     '.qiskit', 'qiskitrc')
"""Default location of the configuration file."""

_ACTIVE_PREFERENCES = {
    'experiment': {'auto_save': lambda val: val.lower() == 'true'}
}
_PREFERENCES_SECTION_NAME = 'ibmq.preferences'


def read_credentials_from_qiskitrc(
        filename: Optional[str] = None
) -> Tuple[Dict[HubGroupProject, Credentials], Dict]:
    """Read a configuration file and return a dictionary with its contents.

    Args:
        filename: Full path to the configuration file. If ``None``, the default
            location is used (``$HOME/.qiskit/qiskitrc``).

    Returns:
        A tuple containing the found credentials and the stored
        preferences, if any, in the configuration file. The format
        for the found credentials is ``{credentials_unique_id: Credentials}``,
        whereas the preferences is ``{credentials_unique_id: {category: {key: val}}}``.

    Raises:
        InvalidCredentialsFormatError: If the file cannot be parsed. Note
            that this exception is not raised if the input file
            does not exist, and an empty dictionary is returned instead.
        HubGroupProjectInvalidStateError: If the default provider stored on
            disk could not be parsed.
    """
    filename = filename or DEFAULT_QISKITRC_FILE
    config_parser = ConfigParser()
    # Preserve case.
    config_parser.optionxform = str  # type: ignore
    try:
        config_parser.read(filename)
    except ParsingError as ex:
        raise InvalidCredentialsFormatError(
            'Error parsing file {}: {}'.format(filename, str(ex))) from ex

    # Build the credentials dictionary.
    credentials_dict: Dict[HubGroupProject, Credentials] = {}
    preferences: Dict[HubGroupProject, Dict] = {}

    for name in config_parser.sections():
        if not name.startswith('ibmq'):
            continue

        single_section = dict(config_parser.items(name))
        configs: Dict[str, Union[str, bool, HubGroupProject, Dict]] = {}

        if name == _PREFERENCES_SECTION_NAME:
            preferences = _parse_preferences(single_section)
            continue

        # Individually convert keys to their right types.
        # TODO: consider generalizing, moving to json configuration or a more
        # robust alternative.
        for key, val in single_section.items():
            if key == 'proxies':
                configs[key] = literal_eval(val)
            elif key == 'verify':
                configs[key] = config_parser[name].getboolean('verify')
            elif key == 'default_provider':
                configs[key] = HubGroupProject.from_stored_format(val)
            else:
                configs[key] = val

        new_credentials = Credentials(**configs)  # type: ignore[arg-type]
        credentials_dict[new_credentials.unique_id()] = new_credentials

    return credentials_dict, preferences


def _parse_preferences(pref_section: Dict) -> Dict[HubGroupProject, Dict]:
    """Parse the preferences section.

    Args:
        pref_section: Preferences section.

    Returns:
        Parsed preferences, indexed by hub/group/project.
    """
    preferences: Dict[HubGroupProject, Dict] = defaultdict(dict)
    for key, val in pref_section.items():
        # Preferences section format is hgp,category,item=value
        elems = key.split(',')
        if len(elems) != 3:
            continue
        hgp, pref_cat, pref_key = elems
        try:
            val_type = _ACTIVE_PREFERENCES[pref_cat][pref_key]
        except KeyError:
            continue
        hgp = HubGroupProject.from_stored_format(hgp)
        cur_val = preferences[hgp].get(pref_cat, {})
        cur_val.update({pref_key: val_type(val)})  # type: ignore[no-untyped-call]
        preferences[hgp].update({pref_cat: cur_val})

    return preferences


def write_qiskit_rc(
        credentials: Dict[HubGroupProject, Credentials],
        preferences: Optional[Dict] = None,
        filename: Optional[str] = None
) -> None:
    """Write credentials to the configuration file.

    Args:
        credentials: Dictionary with the credentials, in the
            ``{credentials_unique_id: Credentials}`` format.
        preferences: Preferences to store.
        filename: Full path to the configuration file. If ``None``, the default
            location is used (``$HOME/.qiskit/qiskitrc``).
    """
    def _credentials_object_to_dict(
            credentials_obj: Credentials,
    ) -> Dict[str, Any]:
        """Convert a ``Credential`` object to a dictionary."""
        credentials_dict = {key: getattr(credentials_obj, key) for key in
                            ['token', 'url', 'proxies', 'verify']
                            if getattr(credentials_obj, key)}

        # Save the default provider to disk, if specified.
        if credentials_obj.default_provider:
            credentials_dict['default_provider'] = \
                credentials_obj.default_provider.to_stored_format()

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
            _credentials_object_to_dict(credentials_object)
        for _, credentials_object in credentials.items()
    }

    if preferences:
        unrolled_pref = {}
        # Preferences section format is hgp,category,key=value.
        # Input preferences format is {hgp: {cat: {pref_key: pref_val}}}.
        for hgp, hgp_val in preferences.items():
            hgp = hgp.to_stored_format()
            for cat, cat_val in hgp_val.items():
                for pref, pref_val in cat_val.items():
                    unrolled_pref[f"{hgp},{cat},{pref}"] = pref_val
        unrolled_credentials[_PREFERENCES_SECTION_NAME] = unrolled_pref

    # Write the configuration file.
    with open(filename, 'w') as config_file:
        config_parser = ConfigParser()
        config_parser.optionxform = str  # type: ignore
        config_parser.read_dict(unrolled_credentials)
        config_parser.write(config_file)


def store_credentials(
        credentials: Credentials,
        overwrite: bool = False,
        filename: Optional[str] = None
) -> None:
    """Store the credentials for a single account in the configuration file.

    Args:
        credentials: Credentials to save.
        overwrite: ``True`` if any existing credentials are to be overwritten.
        filename: Full path to the configuration file. If ``None``, the default
            location is used (``$HOME/.qiskit/qiskitrc``).
    """
    # Read the current providers stored in the configuration file.
    filename = filename or DEFAULT_QISKITRC_FILE
    stored_credentials, stored_preferences = read_credentials_from_qiskitrc(filename)

    # Check if duplicated credentials are already stored. By convention,
    # we assume (hub, group, project) is always unique.
    if credentials.unique_id() in stored_credentials and not overwrite:
        logger.warning('Credentials already present. '
                       'Set overwrite=True to overwrite.')
        return

    # Append and write the credentials to file.
    stored_credentials[credentials.unique_id()] = credentials
    write_qiskit_rc(credentials=stored_credentials, preferences=stored_preferences,
                    filename=filename)


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
    stored_credentials, stored_preferences = read_credentials_from_qiskitrc(filename)

    try:
        del stored_credentials[credentials.unique_id()]
    except KeyError:
        raise CredentialsNotFoundError('The account {} does not exist in the configuration file.'
                                       .format(credentials.unique_id())) from None
    write_qiskit_rc(credentials=stored_credentials, preferences=stored_preferences,
                    filename=filename)


def store_preferences(
        preferences: Dict[HubGroupProject, Dict],
        filename: Optional[str] = None
) -> None:
    """Store the preferences in the configuration file.

    Args:
        preferences: Preferences to save.
        filename: Full path to the configuration file. If ``None``, the default
            location is used (``$HOME/.qiskit/qiskitrc``).
    """
    # Read the current providers stored in the configuration file.
    filename = filename or DEFAULT_QISKITRC_FILE
    stored_credentials, stored_preferences = read_credentials_from_qiskitrc(filename)

    # Merge with existing preferences at category level.
    for hgp, hgp_val in preferences.items():
        merged_hgp = stored_preferences.get(hgp, {})
        merged_hgp.update(hgp_val)
        stored_preferences[hgp] = merged_hgp

    write_qiskit_rc(credentials=stored_credentials, preferences=stored_preferences,
                    filename=filename)
