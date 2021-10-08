# This code is part of Qiskit.
#
# (C) Copyright IBM 2017, 2021.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

from typing import Dict

from qiskit.providers import ProviderV1 as Provider  # type: ignore[attr-defined]

from .ibmqfactory import IBMQFactory
from .runtime.runtime_session import RuntimeSession


class IBMProvider(Provider):

    def __init__(self, token: str = None, url: str = None):
        self._factory = IBMQFactory()
        if token is None:
            self._factory.load_account()
        else:
            self._factory.enable_account(token, url=url)

    def backends(self, name=None, **kwargs):
        """Return a list of backends matching the specified filtering.

        Args:
            name (str): name of the backend.
            **kwargs: dict used for filtering.

        Returns:
            list[Backend]: a list of Backends that match the filtering
                criteria.
        """
        all_backends = {}
        open_provider = None
        for provider in self._factory.providers():
            if provider.credentials.unique_id().to_tuple() == ("ibm-q", "open", "main"):
                open_provider = provider
                continue
            backends = provider.backends(name, **kwargs)
            for backend in backends:
                if backend.name() not in all_backends:
                    all_backends[backend.name()] = backend

        backends = open_provider.backends(name, **kwargs)
        for backend in backends:
            if backend.name() not in all_backends:
                all_backends[backend.name()] = backend

        return list(all_backends.values())

    def open(
            self,
            program: str,
            inputs: Dict,
            options: Dict,
            image: str = ""
    ) -> RuntimeSession:
        """Open a new runtime session.

        Args:
            program: Program ID.
            inputs: Initial program input parameters. These input values are
                persistent throughout the session.
            options: Runtime options that control the execution environment.
                Currently the only available option is ``backend_name``, which is required.
            image: The runtime image used to execute the program, specified in the form
                of image_name:tag. Not all accounts are authorized to select a different image.

        Returns:
            Runtime session.
        """
        backend = self.get_backend(name=options.get("backend_name"))
        return RuntimeSession(backend.provider().runtime,
                              program_id=program,
                              options=options,
                              inputs=inputs,
                              image=image)
