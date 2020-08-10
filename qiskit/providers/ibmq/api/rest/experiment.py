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
        """Account constructor.

        Args:
            session: Session to be used in the adaptor.
            experiment_uuid: UUID of the experiment.
        """
        self.url_prefix = '{}/experiments/{}'.format(url_prefix, experiment_uuid)
        super().__init__(session, self.url_prefix)

    def retrieve(self) -> Dict[str, Any]:
        """Retrieve the specific experiment.

        Returns:
            JSON response.
        """
        url = self.get_url('self')
        return self.session.get(url).json()

    def update(self, experiment):
        """Update an experiment.

        Args:
            experiment: Experiment to upload.

        Returns:
            JSON response.
        """
        url = self.get_url('self')
        return self.session.put(url, json=experiment).json()

    def delete(self):
        """Delete an experiment.

        Returns:
            JSON response.
        """
        url = self.get_url('self')
        return self.session.delete(url).json()

    def upload_plot(self, plot_fn: str):
        """Upload an experiment plot.

        Args:
            plot_fn: Plot file name.

        Returns:
            JSON response.
        """
        files = {'file': (plot_fn, open(plot_fn, 'rb'), 'multipart/form-data')}
        url = self.get_url('plots')
        return self.session.post(url, files=files).json()
