# -*- coding: utf-8 -*-

# This code is part of Qiskit.
#
# (C) Copyright IBM 2017, 2019.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Custom TestCase for IBMQProvider."""

import os
import logging
from unittest import mock

from qiskit.test import QiskitTestCase

# Name of the ibmq provider modules logger.
IBMQ_PROVIDER_LOGGER_NAME = 'qiskit.providers.ibmq'


class IBMQTestCase(QiskitTestCase):
    """Custom TestCase for use with the IBMQProvider."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if os.getenv('LOG_LEVEL'):
            logger_ibmq_provider = logging.getLogger(IBMQ_PROVIDER_LOGGER_NAME)
            if logger_ibmq_provider.level is logging.NOTSET:
                try:
                    logger_ibmq_provider.setLevel(cls.log.level)
                except Exception as ex:
                    logger_ibmq_provider.warning(
                        'Error while trying to set the level for the "%s" logger to %s. %s.',
                        IBMQ_PROVIDER_LOGGER_NAME, os.getenv('LOG_LEVEL'), str(ex))

    def tearDown(self):
        # Reset the default providers, as in practice they acts as a singleton
        # due to importing the wrapper from qiskit.
        from qiskit.providers.ibmq import IBMQ
        IBMQ._providers.clear()
        IBMQ._credentials = None

        from qiskit.providers.basicaer import BasicAer
        BasicAer._backends = BasicAer._verify_backends()

    @classmethod
    def simple_job_callback(cls, job_id, job_status, job, **kwargs):
        """A callback function that logs current job status."""
        # pylint: disable=unused-argument
        queue_info = kwargs.get('queue_info', 'unknown')
        cls.log.info("Job %s status is %s, queue_info is %s", job_id, job_status, queue_info)
