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

"""Analysis result REST adapter."""

import logging
from typing import Dict

from .base import RestAdapterBase
from ..session import RetrySession

logger = logging.getLogger(__name__)


class AnalysisResult(RestAdapterBase):
    """Rest adapter for analysis result related endpoints."""

    URL_MAP = {
        'self': ''
    }

    def __init__(self, session: RetrySession, result_uuid: str, url_prefix: str = '') -> None:
        """AnalysisResult constructor.

        Args:
            session: Session to be used in the adaptor.
            result_uuid: UUID of the analysis result.
            url_prefix: URL prefix.
        """
        self.url_prefix = '{}/analysis_results/{}'.format(url_prefix, result_uuid)
        super().__init__(session, self.url_prefix)

    def update(self, analysis_result: Dict) -> Dict:
        """Update the analysis result.

        Args:
            analysis_result: Analysis result to upload.

        Returns:
            JSON response.
        """
        url = self.get_url('self')
        return self.session.put(url, json=analysis_result).json()

    def delete(self) -> Dict:
        """Delete the analysis result.

        Returns:
            JSON response.
        """
        url = self.get_url('self')
        return self.session.delete(url).json()

    def get(self) -> Dict:
        """Retrieve the analysis result.

        Returns:
            JSON response.
        """
        url = self.get_url('self')
        return self.session.get(url).json()
