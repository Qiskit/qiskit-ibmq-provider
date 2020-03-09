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

"""General utility functions."""

import os
import re
import logging
import keyword
from typing import List, Optional, Type
from logging import Logger


def to_python_identifier(name: str) -> str:
    """Convert a name to a valid Python identifier.

    Args:
        name: Name to be converted.

    Returns:
        Name that is a valid Python identifier.
    """
    # Python identifiers can only contain alphanumeric characters
    # and underscores and cannot start with a digit.
    pattern = re.compile(r"\W|^(?=\d)", re.ASCII)
    if not name.isidentifier():
        name = re.sub(pattern, '_', name)

    # Convert to snake case
    name = re.sub('((?<=[a-z0-9])[A-Z]|(?!^)(?<!_)[A-Z](?=[a-z]))', r'_\1', name).lower()

    while keyword.iskeyword(name):
        name += '_'

    return name


def validate_job_tags(job_tags: Optional[List[str]], exception: Type[Exception]) -> None:
    """Validates input job tags.

    Args:
        job_tags: Job tags to be validated.
        exception: Exception to raise if the tags are invalid.

    Raises:
        Exception: If the job tags are invalid.
    """
    if job_tags and (not isinstance(job_tags, list) or
                     not all(isinstance(tag, str) for tag in job_tags)):
        raise exception("job_tags needs to be a list or strings.")


def setup_logger(logger: Logger) -> None:
    """Setup the logger for the provider modules with the appropriate level.

    It involves:
        * Use the `QISKIT_IBMQ_PROVIDER_LOG_LEVEL` environment variable to
            determine the log level for the provider modules. If it is set, the
            logs will be logged to the console, with the specified level. If it
            is set to an invalid level, the log level defaults to `INFO`. The
            valid log levels are ``DEBUG``, ``INFO``, ``WARNING``, ``ERROR``,
            and ``CRITICAL`` (case-insensitive).
        * Use the `QISKIT_IBMQ_PROVIDER_LOG_FILE` environment variable to
            specify the filename to use for logging the logs to a file. If it is
            not set, the logs will not be logged to a file.
    """
    log_level = os.getenv('QISKIT_IBMQ_PROVIDER_LOG_LEVEL', '')
    log_file = os.getenv('QISKIT_IBMQ_PROVIDER_LOG_FILE', '')

    # Although the log level might not be specified, setup the formatter.
    # This ensures a message is formatted, when logged to the console, in the
    # case it propagates to the root logger.
    log_fmt = ('{}.%(module)s.%(funcName)s:%(levelname)s:%(asctime)s:'
               ' %(message)s'.format(logger.name))
    formatter = logging.Formatter(log_fmt)

    if log_level:
        # Set the logging level, defaulting to `INFO` if it is not a valid level.
        level = logging.getLevelName(log_level.upper())
        if type(level) is not int:
            level = logging.INFO
        logger.setLevel(level)

        if log_file:
            # Set up the file handler.
            file_handler = logging.FileHandler(log_file)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

    # Setup the stream handler, for logging to console, with the given format.
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)
