# -*- coding: utf-8 -*-

# This code is part of Qiskit.
#
# (C) Copyright IBM 2018, 2020.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Root REST adapter."""

import logging
from typing import Dict, List, Any, Union, Optional
from json import JSONDecodeError

from .base import RestAdapterBase
from .experiment import Experiment
from .utils.data_mapper import map_experiment_response

logger = logging.getLogger(__name__)


class Api(RestAdapterBase):
    """Rest adapter for general endpoints."""

    URL_MAP = {
        'login': '/users/loginWithToken',
        'user_info': '/users/me',
        'hubs': '/Network',
        'version': '/version',
        'experiments': '/experiments'
    }

# Function-specific rest adapters.

    def experiment(self, program_uuid: str) -> Experiment:
        """Return an adapter for the experiment.

        Returns:
            The experiment adapter.
        """
        return Experiment(self.session, program_uuid)

# Client functions.

    def hubs(self) -> List[Dict[str, Any]]:
        """Return the list of hub/group/project sets available to the user.

        Returns:
            JSON response.
        """
        url = self.get_url('hubs')
        return self.session.get(url).json()

    def version(self) -> Dict[str, Union[str, bool]]:
        """Return the version information.

        Returns:
            A dictionary with information about the API version,
            with the following keys:

                * ``new_api`` (bool): Whether the new API is being used

            And the following optional keys:

                * ``api-*`` (str): The versions of each individual API component
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

    def login(self, api_token: str) -> Dict[str, Any]:
        """Login with token.

        Args:
            api_token: API token.

        Returns:
            JSON response.
        """
        url = self.get_url('login')
        return self.session.post(url, json={'apiToken': api_token}).json()

    def user_info(self) -> Dict[str, Any]:
        """Return user information.

        Returns:
            JSON response of user information.
        """
        url = self.get_url('user_info')
        response = self.session.get(url).json()

        return response

    def experiments(self, backend_name: Optional[str] = None) -> List:
        """Return experiment data.

        Args:
            backend_name: Name of the backend.

        Returns:
            JSON response.
        """
        url = self.get_url('experiments')
        params = {}
        if backend_name:
            params['device_name'] = backend_name
        raw_data = self.session.get(url, params=params).json()
        mapped_data = []
        for exp in raw_data:
            mapped_data.append(map_experiment_response(exp))

        return mapped_data
