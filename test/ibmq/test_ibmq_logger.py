# -*- coding: utf-8 -*-

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

"""Tests related to logger setup via ``setup_logger()``."""

import os
import logging
from unittest.mock import patch

from qiskit.providers.ibmq.utils.utils import setup_logger

from ..ibmqtestcase import IBMQTestCase


class TestLogger(IBMQTestCase):
    """Tests related to logger setup via ``setup_logger()``."""
    log_level_env = 'QISKIT_IBMQ_PROVIDER_LOG_LEVEL'
    log_file_env = 'QISKIT_IBMQ_PROVIDER_LOG_FILE'

    @classmethod
    def setUpClass(cls):
        """Get a logger to test. Also, cache the initial log level and a file name.

        Note:
            The initial log level is cached in order to restore the log level
            back to the original in `tearDown`.
        """
        cls.logger = logging.getLogger(__name__)
        cls.initial_logger_level = cls.logger.level
        cls.log_file = '{}.log'.format(cls.logger.name)

    def tearDown(self):
        """Restore the original log level and remove the logger handlers.

        Note:
            This essentially "resets" the logger, so it is set back into its
            initial state again for each test.
        """
        self.logger.setLevel(self.initial_logger_level)
        for handler in self.logger.handlers:
            handler.close()
        self.logger.handlers.clear()

    def test_no_log_level(self):
        """Test setting up a logger without a log level.

        Note:
            The log level should default to `NOTSET` when no level is specified.
        """
        default_level_not_set = logging.NOTSET

        with patch.dict('os.environ'):
            if self.log_level_env in os.environ:
                del os.environ[self.log_level_env]
            setup_logger(self.logger)
            self.assertEqual(self.logger.level, default_level_not_set,
                             'The logger level was set to {}, but it should '
                             'be {}'.format(self.logger.level, logging.NOTSET))

    def test_empty_log_level(self):
        """Test setting up a logger with an empty string log level.

        Note:
            The log level should default to `NOTSET` when an empty string is specified.
        """
        default_level_not_set = logging.NOTSET

        with patch.dict('os.environ', {self.log_level_env: ''}):
            setup_logger(self.logger)
            self.assertEqual(self.logger.level, default_level_not_set,
                             'The logger level was set to {}, but it should '
                             'be {}.'.format(self.logger.level, logging.NOTSET))

    def test_invalid_log_level(self):
        """Test setting up a logger with invalid log levels, should default to `WARNING`.

        Note:
              The log level should default to `WARNING` when an invalid level is specified.
        """
        default_level_invalid = logging.WARNING

        invalid_log_levels = ['invalid', 'debugs', 'WarNinGs']
        for invalid_log_level in invalid_log_levels:
            with patch.dict('os.environ', {self.log_level_env: invalid_log_level}):
                setup_logger(self.logger)
                self.assertEqual(self.logger.level, default_level_invalid,
                                 'The logger level was set to {}, but it should '
                                 'be {}.'.format(self.logger.level, logging.WARNING))

    def test_mixed_casing_log_level(self):
        """Test setting up a logger with valid log levels, case insensitive."""
        level_to_set = logging.INFO
        valid_log_levels = ['INFO', 'info', 'InFo']

        for valid_log_level in valid_log_levels:
            with patch.dict('os.environ', {self.log_level_env: valid_log_level}):
                setup_logger(self.logger)
                self.assertEqual(self.logger.level, level_to_set,
                                 'The logger level was set to {}, but it should '
                                 'be {}.'.format(self.logger.level, logging.INFO))

    def test_valid_log_levels(self):
        """Test setting up a logger with all valid levels, case insensitive."""
        all_valid_log_levels = {
            'debug': logging.DEBUG, 'iNFo': logging.INFO,
            'WARNING': logging.WARNING, 'error': logging.ERROR,
            'CRITICAL': logging.CRITICAL}

        for level_name, level_value in all_valid_log_levels.items():
            with patch.dict('os.environ', {self.log_level_env: level_name}):
                setup_logger(self.logger)
                self.assertEqual(self.logger.level, level_value,
                                 'The logger level was set to {}, but it should '
                                 'be {}.'.format(self.logger.level, level_value))

    def test_log_file(self):
        """Test setting up a logger by specifying a file and log level."""
        log_level_warning = ('WARNING', logging.WARNING)
        env_vars_to_patch = {self.log_level_env: log_level_warning[0],
                             self.log_file_env: self.log_file}

        with patch.dict('os.environ', env_vars_to_patch):
            setup_logger(self.logger)
            self.assertEqual(self.logger.level, log_level_warning[1],
                             'The logger level was set to {}, but it should '
                             'be {}.'.format(self.logger.level, log_level_warning[1]))

            # Assert the file handler was created.
            self.assertTrue(self.logger.handlers,
                            'A file handler should have been setup, but it was not.')
            self.assertEqual(len(self.logger.handlers), 1,
                             'Many handlers were setup {}, but it should have only '
                             'been one.'.format(self.logger.handlers))

            # Note that only messages >= `WARNING` will be logged.
            self.logger.debug('This is a debug message that should not be logged in the file.')
            self.logger.warning('This is a warning message that should be logged in the file.')
            self.logger.error('This is a error message that should be logged in the file.')

            # Retrieve the file handler.
            file_handler = self.logger.handlers[0]
            file_path = file_handler.baseFilename

            # Assert the file exists.
            self.assertTrue(os.path.exists(file_path),
                            'The file {} does not exist.'.format(file_path))

            # Assert the messages were logged.
            with open(file_path) as file_:
                content_as_str = file_.read()
                substrings_to_check = {'debug message': False, 'warning message': True,
                                       'error message': True}

                # Check whether the appropriate substrings are in the file.
                for substring, in_file in substrings_to_check.items():
                    if in_file:
                        self.assertIn(substring, content_as_str,
                                      'The substring "{}" was not found in the file {}({}).'
                                      .format(substring, self.log_file, file_path))
                    else:
                        self.assertNotIn(substring, content_as_str,
                                         'The substring "{}" was found in the file {}({}).'
                                         .format('debug message', self.log_file, file_path))

            # Delete the file.
            os.remove(file_path)
