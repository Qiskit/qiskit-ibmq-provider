# -*- coding: utf-8 -*-

# This code is part of Qiskit.
#
# (C) Copyright IBM 2018, 2019.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Version finder for the IBM Q Experience API."""

from json import JSONDecodeError
from typing import Dict, Union

from .base import RestAdapterBase


class VersionFinder(RestAdapterBase):
    """Rest adapter for the version finder."""

    URL_MAP = {
        'version': '/version'
    }

    def version(self) -> Dict[str, Union[str, bool]]:
        """Return the version info.

        Returns:
            a dict with information about the API version,
            with the following keys:
                * `new_api` (bool): whether the new API is being used
            And the following optional keys:
                * `api-*` (str): the versions of each individual API component
        """
        url = self.get_url('version')
        response = self.session.get(url)

        try:
            version_info = response.json()
            version_info['new_api'] = True
        except JSONDecodeError:
            return {
                'new_api': False,
                'api': response.text
            }

        return version_info
