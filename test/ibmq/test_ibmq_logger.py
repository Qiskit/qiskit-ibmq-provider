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
from tempfile import NamedTemporaryFile
from unittest import skipIf, mock

from qiskit.providers.ibmq import (QISKIT_IBMQ_PROVIDER_LOG_LEVEL, QISKIT_IBMQ_PROVIDER_LOG_FILE)
from qiskit.providers.ibmq.utils.utils import setup_logger

from ..ibmqtestcase import IBMQTestCase


class TestLogger(IBMQTestCase):
    """Tests related to logger setup via ``setup_logger()``."""

    def test_no_log_level(self):
        """Test setting up a logger without a log level.

        Note:
            The log level should default to `NOTSET` when no level is specified.
        """
        logger = logging.getLogger(self.id())
        default_level_not_set = logging.NOTSET

        with mock.patch.dict('os.environ'):
            if QISKIT_IBMQ_PROVIDER_LOG_LEVEL in os.environ:
                del os.environ[QISKIT_IBMQ_PROVIDER_LOG_LEVEL]
            setup_logger(logger)
            self.assertEqual(logger.level, default_level_not_set,
                             'The logger level was set to {}, but it should '
                             'be {}'.format(logger.level, default_level_not_set))

    def test_empty_log_level(self):
        """Test setting up a logger with an empty string log level.

        Note:
            The log level should default to `NOTSET` when an empty string is specified.
        """
        logger = logging.getLogger(self.id())
        default_level_not_set = logging.NOTSET

        with mock.patch.dict('os.environ', {QISKIT_IBMQ_PROVIDER_LOG_LEVEL: ''}):
            setup_logger(logger)
            self.assertEqual(logger.level, default_level_not_set,
                             'The logger level was set to {}, but it should '
                             'be {}.'.format(logger.level, default_level_not_set))

    def test_invalid_log_level(self):
        """Test setting up a logger with invalid log levels, should default to `WARNING`.

        Note:
              The log level should default to `WARNING` when an invalid level is specified.
        """
        logger = logging.getLogger(self.id())
        default_level_invalid = logging.WARNING

        invalid_log_levels = ['invalid', 'debugs']
        for invalid_log_level in invalid_log_levels:
            with self.subTest(invalid_log_level=invalid_log_level):
                with mock.patch.dict('os.environ',
                                     {QISKIT_IBMQ_PROVIDER_LOG_LEVEL: invalid_log_level}):
                    setup_logger(logger)
                    self.assertEqual(logger.level, default_level_invalid,
                                     'The logger level was set to {}, but it should '
                                     'be {}.'.format(logger.level, default_level_invalid))

    def test_valid_log_levels_mixed_casing(self):
        """Test setting up a logger with all valid levels, case insensitive."""
        logger = logging.getLogger(self.id())
        all_valid_log_levels = {
            'debug': logging.DEBUG, 'iNFo': logging.INFO,
            'WARNING': logging.WARNING, 'error': logging.ERROR,
            'CRITICAL': logging.CRITICAL}

        for level_name, level_value in all_valid_log_levels.items():
            with self.subTest(level_name=level_name):
                with mock.patch.dict('os.environ', {QISKIT_IBMQ_PROVIDER_LOG_LEVEL: level_name}):
                    setup_logger(logger)
                    self.assertEqual(logger.level, level_value,
                                     'The logger level was set to {}, but it should '
                                     'be {}.'.format(logger.level, level_value))

    # TODO: NamedTemporaryFiles do not support name in Windows
    @skipIf(os.name == 'nt', 'Test not supported in Windows')
    def test_log_file(self):
        """Test setting up a logger by specifying a file and log level."""
        logger = logging.getLogger(self.id())
        log_level_error = ('ERROR', logging.ERROR)

        with NamedTemporaryFile() as temp_log_file:
            # Set the environment variables, including the temp file name.
            env_vars_to_patch = {QISKIT_IBMQ_PROVIDER_LOG_LEVEL: log_level_error[0],
                                 QISKIT_IBMQ_PROVIDER_LOG_FILE: temp_log_file.name}
            with mock.patch.dict('os.environ', env_vars_to_patch):
                setup_logger(logger)

                self.assertEqual(logger.level, log_level_error[1],
                                 'The logger level was set to {}, but it should '
                                 'be {}.'.format(logger.level, log_level_error[1]))

                # Assert the file handler was created.
                self.assertTrue(logger.handlers,
                                'A file handler should have been setup, but it was not.')
                self.assertEqual(len(logger.handlers), 1,
                                 'Many handlers were setup {}, but it should have only '
                                 'been one.'.format(logger.handlers))

                # Note that only messages >= `ERROR` will be logged.
                logger.warning('This is a warning message that should not be logged in the file.')
                logger.error('This is an error message that should be logged in the file.')
                logger.critical('This is a critical message that should be logged in the file.')

                # Assert the file exists.
                log_file_name = os.environ[QISKIT_IBMQ_PROVIDER_LOG_FILE]
                self.assertTrue(os.path.exists(log_file_name),
                                'The file {} does not exist.'.format(log_file_name))

                # Assert the messages were logged.
                with open(temp_log_file.name) as file_:
                    content_as_str = file_.read()

                    # Check whether the appropriate substrings are in the file.
                    substrings_to_check = {'warning message': False, 'error message': True,
                                           'critical message': True}
                    for substring, in_file in substrings_to_check.items():
                        with self.subTest(substring=substring):
                            if in_file:
                                self.assertIn(substring, content_as_str,
                                              'The substring "{}" was not found in the file {}.'
                                              .format(substring, temp_log_file.name))
                            else:
                                self.assertNotIn(substring, content_as_str,
                                                 'The substring "{}" was found in the file {}.'
                                                 .format('debug message', temp_log_file.name))
