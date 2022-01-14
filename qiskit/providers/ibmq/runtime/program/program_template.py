# This code is part of Qiskit.
#
# (C) Copyright IBM 2021.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.
# pylint: disable=unused-argument
# pylint: disable=invalid-name

"""Runtime program template.

The ``main()`` method is the entry point of a runtime program. It takes a
:class:`ProgramBackend` and a :class:`UserMessenger` that can be used to
send circuits to the backend and messages to the user, respectively.
"""

from typing import Any

from qiskit.providers.ibmq.runtime import UserMessenger, ProgramBackend


def program(backend: ProgramBackend, user_messenger: UserMessenger, **kwargs):
    """Function that does classical-quantum calculation."""
    # UserMessenger can be used to publish interim results.
    user_messenger.publish("This is an interim result.")
    return "final result"


def main(backend: ProgramBackend, user_messenger: UserMessenger, **kwargs) -> Any:
    """This is the main entry point of a runtime program.

    The name of this method must not change. It also must have ``backend``
    and ``user_messenger`` as the first two positional arguments.

    Args:
        backend: Backend for the circuits to run on.
        user_messenger: Used to communicate with the program user.
        kwargs: User inputs.

    Returns:
        The final result of the runtime program.
    """
    # Massage the input if necessary.
    result = program(backend, user_messenger, **kwargs)
    # Final results can be directly returned
    return result
