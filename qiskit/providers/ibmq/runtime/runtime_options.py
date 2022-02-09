# This code is part of Qiskit.
#
# (C) Copyright IBM 2022.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Runtime options that control the execution environment."""

import re
import logging
from dataclasses import dataclass
from typing import Optional

from ..exceptions import IBMQInputValueError


@dataclass
class RuntimeOptions:
    """Class for representing runtime execution options.

    Args:
        backend_name: target backend to run on. This is required.
        image: the runtime image used to execute the program, specified in
            the form of ``image_name:tag``. Not all accounts are
            authorized to select a different image.
        log_level: logging level to set in the execution environment. The valid
            log levels are: ``DEBUG``, ``INFO``, ``WARNING``, ``ERROR``, and ``CRITICAL``.
            The default level is ``WARNING``.
    """

    backend_name: str = None
    image: Optional[str] = None
    log_level: Optional[str] = None

    def validate(self) -> None:
        """Validate options.

        Raises:
            IBMQInputValueError: If one or more option is invalid.
        """
        if self.image and not re.match(
                "[a-zA-Z0-9]+([/.\\-_][a-zA-Z0-9]+)*:[a-zA-Z0-9]+([.\\-_][a-zA-Z0-9]+)*$",
                self.image,
        ):
            raise IBMQInputValueError('"image" needs to be in form of image_name:tag')

        if not self.backend_name:
            raise IBMQInputValueError(
                '"backend_name" is required field in "options".'
            )

        if self.log_level and not isinstance(
                logging.getLevelName(self.log_level.upper()), int
        ):
            raise IBMQInputValueError(
                f"{self.log_level} is not a valid log level. The valid log levels are: `DEBUG`, "
                f"`INFO`, `WARNING`, `ERROR`, and `CRITICAL`."
            )
