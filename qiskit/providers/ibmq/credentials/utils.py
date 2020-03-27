# -*- coding: utf-8 -*-

# This code is part of Qiskit.
#
# (C) Copyright IBM 2019.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""General utility functions related to credentials."""

import logging
from typing import Dict, List, Union

from .credentials import Credentials

logger = logging.getLogger(__name__)


def get_provider_as_dict(hgp: str) -> Dict[str, Union[str, None]]:
    """Convert a provider, specified as a string, to a dictionary.

    Args:
        hgp: A provider in the form of "<hub_name>/<group_name>/<project_name>".

    Returns:
        A dictionary in the form {'hub': <hub_name>, 'group': <group_name>,
        'project': <project_name>}. If `hgp` is in the correct format,
        the fields inside the dictionary are given by `hgp`. Otherwise,
        the fields in the dictionary will be set to `None`, indicating the
        default open access project provider.
    """
    hgp_items = hgp.split('/')
    if len(hgp_items) == 3 and all(v for v in hgp_items):
        return {'hub': hgp_items[0], 'group': hgp_items[1], 'project': hgp_items[2]}
    else:
        logger.warning('The specified provider "%s" is invalid. Use the '
                       '"<hub_name>/<group_name>/<project_name>" format.'
                       'The default open access project provider will be used.',
                       hgp)
        return {'hub': None, 'group': None, 'project': None}


def get_provider_as_str(provider_info: Union[Dict[str, str], Credentials]) -> str:
    """Convert a provider, specified within `Credentials` or a dictionary, to a string.

    Args:
        provider_info: A `Credentials` object or dictionary, which contains the
            `hub`, `group`, `project` keys/attributes, respectively.

    Returns:
        A provider in the form "<hub_name>/<group_name>/<project_name>".
    """
    provider_keys = ['hub', 'group', 'project']
    provider_values = []  # type: List[str]
    if isinstance(provider_info, dict):
        provider_values = [provider_info.get(k) for k in provider_keys]
    if isinstance(provider_info, Credentials):
        provider_values = [getattr(provider_info, k) for k in provider_keys]
    return '/'.join(provider_values)
