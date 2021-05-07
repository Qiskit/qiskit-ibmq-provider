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

"""Client for accessing Random Number Generator (RNG) services."""

import logging
from typing import List, Dict, Any

from qiskit.providers.ibmq.credentials import Credentials
from qiskit.providers.ibmq.api.session import RetrySession

from ..rest.random import Random

logger = logging.getLogger(__name__)


class RandomClient:
    """Client for accessing RNG services."""

    def __init__(
            self,
            credentials: Credentials,
    ) -> None:
        """RandomClient constructor.

        Args:
            credentials: Account credentials.
        """
        self._session = RetrySession(credentials.extractor_url, credentials.access_token,
                                     **credentials.connection_parameters())
        self.random_api = Random(self._session)

    def list_services(self) -> List[Dict[str, Any]]:
        """Return RNG services available for this provider.

        Returns:
            RNG services available for this provider.
        """
        return self.random_api.list_services()

    def extract(
            self,
            name: str,
            method: str,
            data: Dict,
            files: Dict
    ) -> Dict:
        """Perform extraction asynchronously.

        Args:
            name: Name of the extractor.
            method: Extractor method.
            data: Encoded extractor parameters.
            files: Raw extractor parameters.

        Returns:
            JSON response.
        """
        return self.random_api.extract(name, method, data, files)

    def job_get(self, job_id: str) -> Dict:
        """Retrieve a job.

        Args:
            job_id: Job ID.

        Returns:
            JSON response.
        """
        return self.random_api.job_get(job_id)

    def get_object_storage(self, url: str) -> Any:
        """Get data from object storage.

        Args:
            url: Object storage URL.

        Returns:
            Response data.
        """
        return self.random_api.get_object_storage(url)
