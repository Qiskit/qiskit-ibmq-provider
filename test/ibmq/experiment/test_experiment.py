# This code is part of Qiskit.
#
# (C) Copyright IBM 2020.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Experiment tests."""

from unittest import SkipTest

from qiskit.providers.ibmq.exceptions import IBMQNotAuthorizedError
from qiskit.providers.ibmq.credentials import read_credentials_from_qiskitrc

from ...ibmqtestcase import IBMQTestCase
from ...decorators import requires_provider
from ...contextmanagers import no_envs, custom_qiskitrc, CREDENTIAL_ENV_VARS


class TestExperimentPreferences(IBMQTestCase):
    """Test experiment preferences."""

    @classmethod
    def setUpClass(cls):
        """Initial class level setup."""
        # pylint: disable=arguments-differ
        super().setUpClass()
        cls.provider = cls._setup_provider()  # pylint: disable=no-value-for-parameter
        try:
            cls.service = cls.provider.service('experiment')
        except IBMQNotAuthorizedError:
            raise SkipTest("Not authorized to use experiment service.")

    @classmethod
    @requires_provider
    def _setup_provider(cls, provider):
        """Get the provider for the class."""
        return provider

    def test_default_preferences(self):
        """Test getting default preferences."""
        self.assertFalse(self.service.preferences['auto_save'])

    def test_set_preferences(self):
        """Test setting preferences."""
        with custom_qiskitrc(), no_envs(CREDENTIAL_ENV_VARS):
            self.service.save_preferences(auto_save=True)
            self.assertTrue(self.service.preferences['auto_save'])

            # Read back from qiskitrc.
            _, stored_pref = read_credentials_from_qiskitrc()
            self.assertTrue(
                stored_pref[self.provider.credentials.unique_id()]['experiment']['auto_save'])
