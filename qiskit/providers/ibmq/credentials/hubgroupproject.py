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

"""Model for representing a hub/group/project tuple."""

from typing import Tuple


class HubGroupProject:
    """Class for representing a hub/group/project.."""

    def __init__(self, hub, group, project) -> None:
        """HubGroupProject constructor."""
        self.hub = hub
        self.group = group
        self.project = project

    @classmethod
    def from_str(cls, hgp: str) -> 'HubGroupProject':
        """Instantiates a ``HubGroupProject`` instance from a string.

        Note:
            The format for the string is ``<hub_name>/<group_name>/<project_name>``.

        Returns:
            A ``HubGroupProject`` instance.
        """
        hub, group, project = hgp.split('/')
        return cls(hub, group, project)

    @classmethod
    def from_credentials(cls, credentials_obj: 'Credentials') -> 'HubGroupProject':
        """Instantiates a ``HubGroupProject`` instance from ``Credentials``.

        Returns:
            A ``HubGroupProject`` instance.
        """
        hub, group, project = [getattr(credentials_obj, key)
                               for key in ['hub', 'group', 'project']]
        return cls(hub, group, project)

    def to_tuple(self) -> Tuple[str, str, str]:
        """Returns ``HubGroupProject`` as a tuple.

        Returns:
            A tuple representation of the hub/group/project.
        """
        return self.hub, self.group, self.project

    def to_stored_format(self) -> str:
        """Returns ``HubGroupProject`` as a string, used to store to disk.

        Note:
            The format of the string returned is ``<hub_name>/<group_name>/<project_name>``.

        Returns:
             A string representation of the hub/group/project, used to store to disk.
        """
        return '/'.join([self.hub, self.group, self.project])
