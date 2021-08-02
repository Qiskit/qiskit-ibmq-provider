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

"""Utilities for working with IBM Quantum experiments."""

from typing import Generator
from contextlib import contextmanager

from .exceptions import IBMExperimentEntryNotFound, IBMExperimentEntryExists
from ..api.exceptions import RequestsApiError
from ..exceptions import IBMQApiError


@contextmanager
def map_api_error(error_msg: str = "") -> Generator[None, None, None]:
    """Convert an ``RequestsApiError`` to a user facing error."""
    try:
        yield
    except RequestsApiError as api_err:
        if api_err.status_code == 409:
            raise IBMExperimentEntryExists(error_msg + f" {api_err}") from None
        if api_err.status_code == 404:
            raise IBMExperimentEntryNotFound(error_msg + f" {api_err}") from None
        raise IBMQApiError(f"Failed to process the request: {api_err}") from None
