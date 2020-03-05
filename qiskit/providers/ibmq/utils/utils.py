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
        * Use the `LOG_LEVEL` environment variable to determine the log level
            for the provider. If it is not set, or is set to an invalid level,
            the log level is defaulted to `INFO` within `setup_test_logging`.
        * Use the `STREAM_LOG` environment variable to determine whether the logs
            should be logged to the console. If it is not set, or set to an invalid
            level, it defaults to `TRUE`. The valid options are `TRUE` and `FALSE`,
            case insensitive.
    """
    from qiskit.test.utils import setup_test_logging

    log_level = os.getenv('LOG_LEVEL', '')
    stream_log = os.getenv('STREAM_LOG', '')
    filename = '{}.log'.format(logger.name)

    if log_level:
        # Ensure the stream logger is set to a valid value. Default to `TRUE` if
        # not set, since log level was specified.
        if stream_log.upper() not in ('TRUE', 'FALSE'):
            stream_log = 'TRUE'
        # Since log level was specified, set stream log, in case it wasn't specified.
        os.environ['STREAM_LOG'] = stream_log
        setup_test_logging(logger, log_level, filename)
