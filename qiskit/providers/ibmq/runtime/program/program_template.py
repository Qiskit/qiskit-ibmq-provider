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

import sys
import json

from qiskit import Aer
from qiskit.providers.ibmq.runtime import UserMessenger, ProgramBackend
from qiskit.providers.ibmq.runtime.utils import RuntimeDecoder


def program(backend: ProgramBackend, user_messenger: UserMessenger, **kwargs):
    """Function that does classical-quantum calculation."""
    # UserMessenger can be used to publish interim results.
    user_messenger.publish("This is an interim result.")
    return "final result"


def main(backend: ProgramBackend, user_messenger: UserMessenger, **kwargs):
    """This is the main entry point of a runtime program.

    Args:
        backend: Backend for the circuits to run on.
        user_messenger: Used to communicate with the program consumer.
        kwargs: User inputs.
    """
    # Massage the input if necessary.
    result = program(backend, user_messenger, **kwargs)
    # UserMessenger can be used to publish final results.
    user_messenger.publish(result, final_result=True)


if __name__ == '__main__':
    # This is used for testing locally using Aer simulator.
    sim_backend = Aer.get_backend('qasm_simulator')
    user_params = {}
    if len(sys.argv) > 1:
        # If there are user parameters.
        user_params = json.loads(sys.argv[1], cls=RuntimeDecoder)
    main(sim_backend, UserMessenger(), **user_params)
