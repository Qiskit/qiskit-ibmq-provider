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
        'upload_plots': '/plots'
    }

    def __init__(self, session: RetrySession, experiment_uuid: str, url_prefix: str = '') -> None:
        """Experiment constructor.

        Args:
            session: Session to be used in the adaptor.
            experiment_uuid: UUID of the experiment.
            url_prefix: URL prefix.
        """
        super().__init__(session, '{}/experiments/{}'.format(url_prefix, experiment_uuid))

    def retrieve(self) -> str:
        """Retrieve the specific experiment.

        Returns:
            Experiment data.
        """
        url = self.get_url('self')
        return self.session.get(url).text

    def update(self, experiment: str) -> Dict:
        """Update the experiment.

        Args:
            experiment: Experiment to update.

        Returns:
            JSON response.
        """
        url = self.get_url('self')
        return self.session.put(url, data=experiment, headers=self._HEADER_JSON_CONTENT).json()

    def delete(self) -> Dict:
        """Delete the experiment.

        Returns:
            JSON response.
        """
        url = self.get_url('self')
        return self.session.delete(url).json()

    def upload_plot(
            self,
            plot: Union[bytes, str],
            plot_name: str,
            sync_upload: bool = True
    ) -> Dict:
        """Upload a plot for the experiment.

        Args:
            plot: Plot file name or data to upload.
            plot_name: Name of the plot.
            sync_upload: By default the server will upload the plot file
                to backend storage asynchronously. Set this to False to use
                that behavior and not block the upload.

        Returns:
            JSON response.
        """
        url = self.get_url('upload_plots')
        headers = {
            'x-sync-upload': str(sync_upload)
        }
        if isinstance(plot, str):
            with open(plot, 'rb') as file:
                data = {'plot': (plot_name, file)}
                response = self.session.post(url, files=data, headers=headers).json()
        else:
            data = {'plot': (plot_name, plot)}  # type: ignore[dict-item]
            response = self.session.post(url, files=data, headers=headers).json()

        return response


class ExperimentPlot(RestAdapterBase):
    """Rest adapter for experiment plot related endpoints."""

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
            plot_name: Name of the plot.
            url_prefix: URL prefix.
        """
        super().__init__(session, '{}/experiments/{}/plots/{}'.format(
            url_prefix, experiment_uuid, plot_name))
        self.plot_name = plot_name

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

    def update(
            self,
            plot: Union[bytes, str],
            sync_upload: bool = True
    ) -> Dict:
        """Update an experiment plot.

        Args:
            plot: Plot file name or data to upload.
            sync_upload: By default the server will upload the plot file
                to backend storage asynchronously. Set this to False to use
                that behavior and not block the upload.

        Returns:
            JSON response.
        """
        url = self.get_url('self')
        headers = {
            'x-sync-upload': str(sync_upload)
        }
        if isinstance(plot, str):
            with open(plot, 'rb') as file:
                data = {'plot': (self.plot_name, file)}
                response = self.session.put(url, files=data, headers=headers).json()
        else:
            data = {'plot': (self.plot_name, plot)}  # type: ignore[dict-item]
            response = self.session.put(url, files=data, headers=headers).json()

        return response
