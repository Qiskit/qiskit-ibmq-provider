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

"""Qiskit runtime job."""

from typing import Dict, Any
import copy
from functools import wraps

from .ibm_runtime_service import IBMRuntimeService


def _active_session(func):  # type: ignore
    """Decorator used to ensure the session is active."""

    @wraps(func)
    def _wrapper(self, *args, **kwargs):  # type: ignore
        if not self._active:
            raise RuntimeError("The session is closed.")
        return func(self, *args, **kwargs)

    return _wrapper


class RuntimeSession:

    def __init__(
            self,
            runtime: IBMRuntimeService,
            program_id: str,
            options: Dict,
            inputs: Dict,
            image: str = ""
    ):
        """RuntimeSession constructor.

        Args:
            runtime: Runtime service.
            program_id: Program ID.
            options: Runtime options.
            inputs: Initial program inputs.
            image: The runtime image to use, specified in the form of image_name:tag.
        """
        self._service = runtime
        self._program_id = program_id
        self._options = options
        self._initial_inputs = inputs
        self._job = None
        self._active = True
        self._image = image

    @_active_session
    def write(self, **kwargs: Dict) -> None:
        """Write to the session."""
        inputs = copy.copy(self._initial_inputs)
        inputs.update(kwargs)
        self._job = self._service.run(
            program_id=self._program_id,
            options=self._options,
            inputs=inputs,
            image=self._image
        )

    @_active_session
    def read(self) -> Any:
        """Read from the session.

        Returns:
            Data returned from the session.
        """
        return self._job.result()

    def info(self) -> Dict:
        """Return session information.

        Returns:
            Session information.
        """
        out = {"backend": self._options.get("backend_name", "unknown")}
        if self._job:
            out["job id"] = self._job.job_id()
            out["job status"] = self._job.status()
        return out

    def close(self) -> None:
        """Close the session."""
        self._active = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._active = False
