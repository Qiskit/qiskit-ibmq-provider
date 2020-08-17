# -*- coding: utf-8 -*-

# This code is part of Qiskit.
#
# (C) Copyright IBM 2020.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Experiment REST adapter."""

import logging
from typing import Dict, Any


from .base import RestAdapterBase
from ..session import RetrySession

logger = logging.getLogger(__name__)


class Experiment(RestAdapterBase):
    """Rest adapter for experiment related endpoints."""

    URL_MAP = {
        'self': '',
        'plots': '/plots'
    }

    def __init__(self, session: RetrySession, experiment_uuid: str, url_prefix: str = '') -> None:
        """Experiment constructor.

        Args:
            session: Session to be used in the adaptor.
            experiment_uuid: UUID of the experiment.
            url_prefix: URL prefix.
        """
        self.url_prefix = '{}/experiments/{}'.format(url_prefix, experiment_uuid)
        super().__init__(session, self.url_prefix)

    def retrieve(self) -> Dict:
        """Retrieve the specific experiment.

        Returns:
            JSON response.
        """
        url = self.get_url('self')
        return self.session.get(url).json()

    def update(self, experiment: Dict) -> Dict:
        """Update the experiment.

        Args:
            experiment: Experiment to update.

        Returns:
            JSON response.
        """
        url = self.get_url('self')
        return self.session.put(url, json=experiment).json()

    def delete(self) -> Dict:
        """Delete the experiment.

        Returns:
            JSON response.
        """
        url = self.get_url('self')
        return self.session.delete(url).json()

    def upload_plot(self, plot_fn: str) -> Dict:
        """Upload a plot for the experiment.

        Args:
            plot_fn: Plot file name.

        Returns:
            JSON response.
        """
        files = {'file': (plot_fn, open(plot_fn, 'rb'), 'multipart/form-data')}
        url = self.get_url('plots')
        return self.session.post(url, files=files).json()
