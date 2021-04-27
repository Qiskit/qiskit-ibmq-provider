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

"""Base class for handling communication with program consumers."""

import json
from typing import Any

from ..utils import RuntimeEncoder


class UserMessenger:
    """Base class for handling communication with program consumers.

    A program consumer is the user that executes the runtime program.
    """

    def publish(
            self,
            message: Any,
            encoder: json.JSONEncoder = RuntimeEncoder,  # type: ignore[assignment]
            final: bool = False
    ) -> None:
        """Publish message.

        You can use this method to publish messages, such as interim and final results,
        to the program consumer. The messages will be made immediately available to the consumer,
        but they may choose not to receive the messages.

        The `final` parameter is used to indicate whether the message is
        the final result of the program. Final results may be processed differently
        from interim results.

        Args:
            message: Message to be published. Can be any type.
            encoder: An optional JSON encoder for serializing
            final: Whether the message being published is the final result.
        """
        # pylint: disable=unused-argument
        # Default implementation for testing.
        print(json.dumps(message, cls=encoder))
