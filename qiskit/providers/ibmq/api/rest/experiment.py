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
from typing import Dict, Union

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

    def upload_plot(self, plot: Union[bytes, str], plot_name: str) -> Dict:
        """Upload a plot for the experiment.

        Args:
            plot: Plot file name or data to upload.
            plot_name: Name of the plot.

        Returns:
            JSON response.
        """
        url = self.get_url('plots')
        if isinstance(plot, str):
            with open(plot, 'rb') as file:
                data = {'plot': (plot_name, file)}
                response = self.session.post(url, files=data).json()
        else:
            data = {'plot': (plot_name, plot)}
            response = self.session.post(url, files=data).json()

        return response


class ExperimentPlot(Experiment):

    URL_MAP = {
        'self': ''
    }

    def __init__(
            self,
            session: RetrySession,
            experiment_uuid: str,
            plot_name: str,
            url_prefix: str = '') -> None:
        """Experiment constructor.

        Args:
            session: Session to be used in the adaptor.
            experiment_uuid: UUID of the experiment.
            url_prefix: URL prefix.
        """
        super().__init__(session, experiment_uuid, url_prefix)
        self.prefix_url += '/plots/{}'.format(plot_name)

    def retrieve(self) -> bytes:
        """Retrieve the specific experiment plot.

        Returns:
            Plot content.
        """
        url = self.get_url('self')
        response = self.session.get(url)
        return response.content

    def delete(self) -> None:
        """Delete this experiment plot."""
        url = self.get_url('self')
        self.session.delete(url)

