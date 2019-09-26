# -*- coding: utf-8 -*-

# This code is part of Qiskit.
#
# (C) Copyright IBM 2019.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Backend namespace for an IBM Quantum Experience account provider."""

from typing import Iterable
from types import SimpleNamespace

from .ibmqbackend import IBMQBackend
from .api.exceptions import RequestsApiError
from .utils import to_python_identifier


class ProviderBackends(SimpleNamespace):
    """Backend namespace for an IBM Quantum Experience account provider."""

    def __init__(self, provider: 'AccountProvider') -> None:
        """Creates a new ProviderBackends instance.

        Args:
            provider (AccountProvider): IBM Q Experience account provider
        """
        self._provider = provider
        self._initialized = False
        super().__init__()

    def _discover_backends(self) -> None:
        """Discovers the remote backends if not already known."""
        if not self._initialized:
            try:
                for backend in self._provider.backends(timeout=3):
                    backend_name = to_python_identifier(backend.name())

                    # Append _ if duplicate
                    while backend_name in self.__dict__:
                        backend_name += '_'

                    setattr(self, backend_name, backend)
                self._initialized = True
            except RequestsApiError:
                # Ignore any networking errors since this is a convenience
                # feature meant for interactive sessions.
                pass

    def __dir__(self) -> Iterable[str]:
        self._discover_backends()
        return super().__dir__()

    def __getattr__(self, item: str) -> IBMQBackend:
        self._discover_backends()
        return super().__getattribute__(item)
