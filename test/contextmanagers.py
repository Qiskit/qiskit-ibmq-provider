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

"""Context managers for using with IBMQProvider unit tests."""

import os
from typing import Optional, Dict
from contextlib import ContextDecorator, contextmanager
from tempfile import NamedTemporaryFile
from unittest.mock import patch

from qiskit.providers.ibmq.credentials import configrc, Credentials
from qiskit.providers.ibmq.credentials.environ import VARIABLES_MAP
from qiskit.providers.ibmq import IBMQFactory


CREDENTIAL_ENV_VARS = VARIABLES_MAP.keys()


class custom_envs(ContextDecorator):
    """Context manager that modifies environment variables."""
    # pylint: disable=invalid-name

    def __init__(self, new_environ):
        """custom_envs constructor.

        Args:
            new_environ (dict): a dictionary of new environment variables to
                use.
        """
        self.new_environ = new_environ
        self.os_environ_original = os.environ.copy()

    def __enter__(self):
        # Remove the original variables from `os.environ`.
        modified_environ = {**os.environ, **self.new_environ}
        os.environ = modified_environ

    def __exit__(self, *exc):
        os.environ = self.os_environ_original


class no_envs(ContextDecorator):
    """Context manager that disables environment variables."""
    # pylint: disable=invalid-name

    def __init__(self, vars_to_remove):
        """no_envs constructor.

        Args:
            vars_to_remove (list): environment variables to remove.
        """
        self.vars_to_remove = vars_to_remove
        self.os_environ_original = os.environ.copy()

    def __enter__(self):
        # Remove the original variables from `os.environ`.
        modified_environ = {key: value for key, value in os.environ.items()
                            if key not in self.vars_to_remove}
        os.environ = modified_environ

    def __exit__(self, *exc):
        os.environ = self.os_environ_original


class custom_qiskitrc(ContextDecorator):
    """Context manager that uses a temporary qiskitrc."""
    # pylint: disable=invalid-name

    def __init__(self, contents=b''):
        # Create a temporary file with the contents.
        self.tmp_file = NamedTemporaryFile()
        self.tmp_file.write(contents)
        self.tmp_file.flush()
        self.default_qiskitrc_file_original = configrc.DEFAULT_QISKITRC_FILE

    def __enter__(self):
        # Temporarily modify the default location of the qiskitrc file.
        configrc.DEFAULT_QISKITRC_FILE = self.tmp_file.name
        return self

    def __exit__(self, *exc):
        # Delete the temporary file and restore the default location.
        self.tmp_file.close()
        configrc.DEFAULT_QISKITRC_FILE = self.default_qiskitrc_file_original


class no_file(ContextDecorator):
    """Context manager that disallows access to a file."""
    # pylint: disable=invalid-name

    def __init__(self, filename):
        self.filename = filename
        # Store the original `os.path.isfile` function, for mocking.
        self.isfile_original = os.path.isfile
        self.patcher = patch('os.path.isfile', side_effect=self.side_effect)

    def __enter__(self):
        self.patcher.start()

    def __exit__(self, *exc):
        self.patcher.stop()

    def side_effect(self, filename_):
        """Return False for the specified file."""
        if filename_ == self.filename:
            return False
        return self.isfile_original(filename_)


def _mocked_initialize_provider(
        self,
        credentials: Credentials,
        preferences: Optional[Dict] = None
) -> None:
    """Mock ``_initialize_provider()``, just storing the credentials."""
    self._credentials = credentials
    if preferences:
        credentials.preferences = preferences.get(credentials.unique_id(), {})


@contextmanager
def mock_ibmq_provider():
    """Mock the initialization of ``IBMQFactory``, so it does not query the API."""
    patcher = patch.object(IBMQFactory, '_initialize_providers',
                           side_effect=_mocked_initialize_provider,
                           autospec=True)
    patcher2 = patch.object(IBMQFactory, '_check_api_version',
                            return_value={'new_api': True, 'api-auth': '0.1'})
    patcher.start()
    patcher2.start()
    yield
    patcher2.stop()
    patcher.stop()
