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

"""Job limit information related to a backend."""

from typing import Any
from types import SimpleNamespace


class BackendJobLimit(SimpleNamespace):
    """Job limit for a backend.

    Represent the job limit for a backend on a specific provider. This
    instance is returned by the :meth:`IBMQBackend.job_limit()<IBMQBackend.job_limit>`
    method.

    Attributes:
        maximum_jobs: The current number of active jobs on this backend, with
            this provider.
        running_jobs: The current number of active jobs on this backend, with
            this provider.
    """

    def __init__(self, maximum_jobs: int, running_jobs: int, **kwargs: Any) -> None:
        """BackendJobLimit constructor.

        Args:
            maximum_jobs: The maximum number of concurrent jobs this account is
                allowed to submit to this backend, with this provider.
            running_jobs: The current number of active jobs on this backend, with
                this provider.
            kwargs: Additional attributes that will be added as instance members.
        """
        self.maximum_jobs = maximum_jobs
        self.active_jobs = running_jobs

        super().__init__(**kwargs)
