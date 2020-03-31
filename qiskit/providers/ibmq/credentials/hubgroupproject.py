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

from collections import namedtuple

from .exceptions import HubGroupProjectValueError, InvalidFormatHubGroupProjectError

HubGroupProjectTuple = namedtuple('HubGroupProjectTuple',
                                  ['hub', 'group', 'project'])


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
    def from_str(cls, hgp: str) -> 'HubGroupProject':
        """Instantiates a ``HubGroupProject`` instance from a string.

        Note:
            The format for the string is ``<hub_name>/<group_name>/<project_name>``.

        Raises:
            HubGroupProjectValueError: If the specified string, used for conversion, is
                in an invalid format.

        Returns:
            A ``HubGroupProject`` instance.
        """
        try:
            hub, group, project = hgp.split('/')
            if (not hub) or (not group) or (not project):
                raise HubGroupProjectValueError(
                    'The hub/group/project specified "{}" is in an invalid format. '
                    'Every field must be specified: hub = "{}", group = "{}", project = "{}".'
                    .format(hgp, hub, group, project))
        except ValueError:
            # Not enough, or too many, values were provided
            raise HubGroupProjectValueError(
                'The hub/group/project specified "{}" is in an invalid format. '
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

    def to_tuple(self) -> HubGroupProjectTuple:
        """Returns ``HubGroupProject`` as a tuple.

        Returns:
            A tuple representation of the hub/group/project.
        """
        return HubGroupProjectTuple(self.hub, self.group, self.project)

    def to_stored_format(self) -> str:
        """Returns ``HubGroupProject`` as a string, used to store to disk.

        Note:
            The format of the string returned is ``<hub_name>/<group_name>/<project_name>``.

        Raises:
            InvalidFormatHubGroupProjectError: If the ``HubGroupProject`` cannot be
                represented as a string to store on disk (i.e. the hub, group, project
                fields are empty strings or ``None``).

        Returns:
             A string representation of the hub/group/project, used to store to disk.
        """
        if (not self.hub) or (not self.group) or (not self.project):
            raise InvalidFormatHubGroupProjectError(
                'The hub/group/project cannot be stored because it is in an invalid format. '
                'Every field must be specified: hub = "{}", group = "{}", project = "{}".')
        return '/'.join([self.hub, self.group, self.project])
