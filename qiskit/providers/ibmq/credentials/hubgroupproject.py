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

from typing import Tuple, Optional

from .exceptions import HubGroupProjectInvalidStateError


class HubGroupProject:
    """Class for representing a hub/group/project."""

    def __init__(
            self,
            hub: str = None,
            group: str = None,
            project: str = None
    ) -> None:
        """HubGroupProject constructor."""
        self.hub = hub
        self.group = group
        self.project = project

    @classmethod
    def from_stored_format(cls, hgp: str) -> 'HubGroupProject':
        """Instantiates a ``HubGroupProject`` instance from a string.

        Note:
            The format for the string is ``<hub_name>/<group_name>/<project_name>``.
            It is saved inside the configuration file to specify a default provider.

        Raises:
            HubGroupProjectInvalidStateError: If the specified string, used for conversion, is
                in an invalid format.

        Returns:
            A ``HubGroupProject`` instance.
        """
        try:
            hub, group, project = hgp.split('/')
            if (not hub) or (not group) or (not project):
                raise HubGroupProjectInvalidStateError(
                    'The hub/group/project "{}" is in an invalid format. '
                    'Every field must be specified: hub = "{}", group = "{}", project = "{}".'
                    .format(hgp, hub, group, project))
        except ValueError:
            # Not enough, or too many, values were provided.
            raise HubGroupProjectInvalidStateError(
                'The hub/group/project "{}" is in an invalid format. '
                'Use the "<hub_name>/<group_name>/<project_name>" format.'
                .format(hgp))

        return cls(hub, group, project)

    @classmethod
    def from_credentials(
            cls,
            credentials_obj: 'Credentials'  # type: ignore
    ) -> 'HubGroupProject':
        """Instantiates a ``HubGroupProject`` instance from ``Credentials``.

        Returns:
            A ``HubGroupProject`` instance.
        """
        hub, group, project = [getattr(credentials_obj, key)
                               for key in ['hub', 'group', 'project']]
        return cls(hub, group, project)

    def to_stored_format(self) -> str:
        """Returns ``HubGroupProject`` as a string.

        Note:
            The format of the string returned is ``<hub_name>/<group_name>/<project_name>``.
            It is used to save a default provider in the configuration file.

        Raises:
            HubGroupProjectInvalidStateError: If the ``HubGroupProject`` cannot be
                represented as a string to store on disk (i.e. Some of the hub, group,
                project fields are empty strings or ``None``).

        Returns:
             A string representation of the hub/group/project, used to store to disk.
        """
        if (not self.hub) or (not self.group) or (not self.project):
            raise HubGroupProjectInvalidStateError(
                'The hub/group/project cannot be represented in the stored format. '
                'Every field must be specified: hub = "{}", group = "{}", project = "{}".'
                .format(self.hub, self.group, self.project))
        return '/'.join([self.hub, self.group, self.project])

    def to_tuple(self) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Returns ``HubGroupProject`` as a tuple."""
        return self.hub, self.group, self.project

    def __eq__(self, other: 'HubGroupProject') -> bool:  # type: ignore
        """Two instances are equal if they define the same hub, group, project."""
        return (self.hub, self.group, self.project) == (other.hub, other.group, other.project)

    def __hash__(self) -> int:
        """Returns a hash for an instance."""
        return hash((self.hub, self.group, self.project))
