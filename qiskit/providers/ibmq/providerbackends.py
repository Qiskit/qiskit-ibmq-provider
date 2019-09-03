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

import re
import keyword
from typing import Iterable, Any
from types import SimpleNamespace

from .ibmqbackend import IBMQBackend
from .api_v2.exceptions import RequestsApiError


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
                # Python identifiers can only contain alphanumeric characters
                # and underscores and cannot start with a digit.
                pattern = re.compile(r"\W|^(?=\d)", re.ASCII)
                for backend in self._provider.backends(timeout=3):
                    backend_name = backend.name()

                    # Make it a valid identifier
                    if not backend_name.isidentifier():
                        backend_name = re.sub(pattern, '_', backend_name)

                    # Append _ if is keyword or duplicate
                    while keyword.iskeyword(backend_name) or backend_name in self.__dict__:
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

    def __getattr__(self, item) -> IBMQBackend:
        self._discover_backends()
        return super().__getattribute__(item)
