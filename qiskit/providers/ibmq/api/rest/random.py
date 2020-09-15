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

"""Random REST adapter."""

import logging
from typing import Dict, List, Any

from qiskit.providers.ibmq.api.rest.base import RestAdapterBase

logger = logging.getLogger(__name__)


class Random(RestAdapterBase):
    """Rest adapter for RNG related endpoints."""

    URL_MAP = {
        'list_extractors': '/extractors',
        'extract': '/extractors/{}/{}'
    }

    def list_services(self) -> List[Dict[str, Any]]:
        """Return a list of RNG services.

        Returns:
            JSON response.
        """
        url = self.get_url('list_extractors')
        return self.session.get(url).json()

    def extract(
            self,
            name: str,
            method: str,
            data: Dict,
            files: Dict
    ) -> Any:
        """

        Args:
            name: Name of the extractor.
            method: Extractor method.
            data: Encoded extractor parameters.
            files: Raw extractor parameters.

        Returns:
            Response data.
        """
        url = self.get_url('extract').format(name, method)
        response = self.session.post(url, data=data, files=files, timeout=600)
        return response.content
