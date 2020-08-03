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

"""Experiment REST adapter."""

import logging
from typing import Dict, Any


from .base import RestAdapterBase
from .utils.data_mapper import map_experiment_response
from ..session import RetrySession

logger = logging.getLogger(__name__)


class Experiment(RestAdapterBase):
    """Rest adapter for hub/group/project related endpoints."""

    URL_MAP = {
        'self': '',
        'plots': '/plots'
    }

    def __init__(self, session: RetrySession, program_uuid: str, url_prefix: str = '') -> None:
        """Account constructor.

        Args:
            session: Session to be used in the adaptor.
            program_uuid: UUID of the experiment.
        """
        self.url_prefix = '{}/experiments/{}'.format(url_prefix, program_uuid)
        super().__init__(session, self.url_prefix)

    def get_experiment(self) -> Dict[str, Any]:
        """Get the specific experiment.

        Returns:
            JSON response.
        """
        url = self.get_url('self')
        raw_data = self.session.get(url).json()
        return map_experiment_response(raw_data)

    def upload_experiment(self, experiment):
        """Upload the experiment.

        Args:
            experiment: Experiment to upload.
        """
        url = self.get_url('self')
        self.session.put(url, experiment)

