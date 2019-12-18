# -*- coding: utf-8 -*-

# This code is part of Qiskit.
#
# (C) Copyright IBM 2017, 2019.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Queue information related to a job."""

from typing import Any, Optional
from datetime import datetime

from qiskit.validation import BaseModel, bind_schema

from qiskit.providers.ibmq.api.rest.validation import InfoQueueResponseSchema


@bind_schema(InfoQueueResponseSchema)
class QueueInfo(BaseModel):
    """Queue information related to a job."""

    def __init__(
            self,
            position: Optional[int],
            _status: Optional[str],
            estimated_start_time: Optional[datetime],
            estimated_complete_time: Optional[datetime],
            hub_priority: Optional[float],
            group_priority: Optional[float],
            project_priority: Optional[float],
            **kwargs: Any
    ) -> None:
        """Creates a new QueueInfo instance.

        Args:
            position: Position in the queue.
            _status: Job status.
            estimated_start_time: Estimated start time for the job, in UTC.
            estimated_complete_time: Estimated complete time for the job, in UTC.
            hub_priority: Dynamic priority for the hub.
            group_priority: Dynamic priority for the group.
            project_priority: Dynamic priority for the project.
            kwargs: additional attributes that will be added as instance members.
        """
        self.position = position
        self._status = _status
        self.estimated_start_time = estimated_start_time
        self.estimated_complete_time = estimated_complete_time
        self.hub_priority = hub_priority
        self.group_priority = group_priority
        self.project_priority = project_priority

        super().__init__(**kwargs)
