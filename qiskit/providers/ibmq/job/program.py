# -*- coding: utf-8 -*-

# This code is part of Qiskit.
#
# (C) Copyright IBM 2017, 2020.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""IBM Quantum Experience job."""

import uuid
from datetime import datetime
from typing import Dict

from dateutil import tz


class Program:

    def __init__(
            self,
            device_name,
            created_at=None,
            end_time=None,
            extra=None,
            start_time=None,
            tags=None,
            program_type=None,
            updated_at=None,
            program_uuid=None
    ):
        self.backend_name = device_name
        self.uuid = program_uuid or uuid.uuid4()
        self.creation_datetime = created_at or datetime.now(tz=tz.tzlocal())
        self.start_datetime = start_time
        self.end_datetime = end_time
        self.extra = extra or {}
        self.tags = tags or []
        self.type = program_type
        self.updated_datetime = updated_at

        pass

    @classmethod
    def from_dict(cls, data: Dict) -> 'Program':
        """Create a new Program object from a dictionary.

        Args:
            data: A dictionary representing the Program.

        Returns:
            A new Program object.
        """
        return cls(**data)
