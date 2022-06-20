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
import copy
from typing import List, Optional, Type, Any, Dict, Union, Tuple
from threading import Condition
from queue import Queue

from qiskit.providers.jobstatus import JobStatus

from ..apiconstants import ApiJobStatus


API_TO_JOB_STATUS = {
    ApiJobStatus.CREATING: JobStatus.INITIALIZING,
    ApiJobStatus.CREATED: JobStatus.INITIALIZING,
    ApiJobStatus.TRANSPILING: JobStatus.INITIALIZING,
    ApiJobStatus.TRANSPILED: JobStatus.INITIALIZING,
    ApiJobStatus.VALIDATING: JobStatus.VALIDATING,
    ApiJobStatus.VALIDATED: JobStatus.VALIDATING,
    ApiJobStatus.RUNNING: JobStatus.RUNNING,
    ApiJobStatus.PENDING_IN_QUEUE: JobStatus.QUEUED,
    ApiJobStatus.QUEUED: JobStatus.QUEUED,
    ApiJobStatus.COMPLETED: JobStatus.DONE,
    ApiJobStatus.CANCELLED: JobStatus.CANCELLED,
    ApiJobStatus.ERROR_CREATING_JOB: JobStatus.ERROR,
    ApiJobStatus.ERROR_VALIDATING_JOB: JobStatus.ERROR,
    ApiJobStatus.ERROR_RUNNING_JOB: JobStatus.ERROR,
    ApiJobStatus.ERROR_TRANSPILING_JOB: JobStatus.ERROR
}


def api_status_to_job_status(api_status: Union[str, ApiJobStatus]) -> JobStatus:
    """Return the corresponding job status for the input server job status.

    Args:
        api_status: Server job status.

    Returns:
        Job status.
    """
    if isinstance(api_status, str):
        api_status = ApiJobStatus(api_status.upper())
    return API_TO_JOB_STATUS[api_status]


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


def setup_logger(logger: logging.Logger) -> None:
    """Setup the logger for the provider modules with the appropriate level.

    It involves:
        * Use the `QISKIT_IBMQ_PROVIDER_LOG_LEVEL` environment variable to
          determine the log level to use for the provider modules. If an invalid
          level is set, the log level defaults to ``WARNING``. The valid log levels
          are ``DEBUG``, ``INFO``, ``WARNING``, ``ERROR``, and ``CRITICAL``
          (case-insensitive). If the environment variable is not set, then the parent
          logger's level is used, which also defaults to `WARNING`.
        * Use the `QISKIT_IBMQ_PROVIDER_LOG_FILE` environment variable to specify the
          filename to use when logging messages. If a log file is specified, the log
          messages will not be logged to the screen. If a log file is not specified,
          the log messages will only be logged to the screen and not to a file.
    """
    log_level = os.getenv('QISKIT_IBMQ_PROVIDER_LOG_LEVEL', '')
    log_file = os.getenv('QISKIT_IBMQ_PROVIDER_LOG_FILE', '')

    # Setup the formatter for the log messages.
    log_fmt = '%(module)s.%(funcName)s:%(levelname)s:%(asctime)s: %(message)s'
    formatter = logging.Formatter(log_fmt)

    # Set propagate to `False` since handlers are to be attached.
    logger.propagate = False

    # Log messages to a file (if specified), otherwise log to the screen (default).
    if log_file:
        # Setup the file handler.
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    else:
        # Setup the stream handler, for logging to console, with the given format.
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)

    # Set the logging level after formatting, if specified.
    if log_level:
        # Default to `WARNING` if the specified level is not valid.
        level = logging.getLevelName(log_level.upper())
        if not isinstance(level, int):
            logger.warning('"%s" is not a valid log level. The valid log levels are: '
                           '`DEBUG`, `INFO`, `WARNING`, `ERROR`, and `CRITICAL`.', log_level)
            level = logging.WARNING
        logger.debug('The logger is being set to level "%s"', level)
        logger.setLevel(level)


def filter_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Return the data with certain fields filtered.

    Data to be filtered out includes hub/group/project information.

    Args:
        data: Original data to be filtered.

    Returns:
        Filtered data.
    """
    if not isinstance(data, dict):
        return data

    data_to_filter = copy.deepcopy(data)
    keys_to_filter = ['hubInfo']
    _filter_value(data_to_filter, keys_to_filter)  # type: ignore[arg-type]
    return data_to_filter


def _filter_value(data: Dict[str, Any], filter_keys: List[Union[str, Tuple[str, str]]]) -> None:
    """Recursive function to filter out the values of the input keys.

    Args:
        data: Data to be filtered
        filter_keys: A list of keys whose values are to be filtered out. Each
            item in the list can be a string or a tuple. A tuple indicates nested
            keys, such as ``{'backend': {'name': ...}}`` and must have a length
            of 2.
    """
    for key, value in data.items():
        for filter_key in filter_keys:
            if isinstance(filter_key, str) and key == filter_key:
                data[key] = '...'
            elif key == filter_key[0] and filter_key[1] in value:
                data[filter_key[0]][filter_key[1]] = '...'
            elif isinstance(value, dict):
                _filter_value(value, filter_keys)


class RefreshQueue(Queue):
    """A queue that replaces the oldest item with the new item being added when full.

    A FIFO queue with a bounded size. Once the queue is full, when a new item
    is being added, the oldest item on the queue is discarded to make space for
    the new item.
    """

    def __init__(self, maxsize: int):
        """RefreshQueue constructor.

        Args:
            maxsize: Maximum size of the queue.
        """
        self.condition = Condition()
        super().__init__(maxsize=maxsize)

    def put(self, item: Any) -> None:  # type: ignore[override]
        """Put `item` into the queue.

        If the queue is full, the oldest item is replaced by `item`.

        Args:
            item: Item to put into the queue.
        """
        # pylint: disable=arguments-differ

        with self.condition:
            if self.full():
                super().get(block=False)
            super().put(item, block=False)
            self.condition.notify()

    def get(self, block: bool = True, timeout: Optional[float] = None) -> Any:
        """Remove and return an item from the queue.

        Args:
            block: If ``True``, block if necessary until an item is available.
            timeout: Block at most `timeout` seconds before raising the
                ``queue.Empty`` exception if no item was available. If
                ``None``, block indefinitely until an item is available.

        Returns:
            An item from the queue.

        Raises:
            queue.Empty: If `block` is ``False`` and no item is available, or
                if `block` is ``True`` and no item is available before `timeout`
                is reached.
        """
        with self.condition:
            if block and self.empty():
                self.condition.wait(timeout)
            return super().get(block=False)

    def notify_all(self) -> None:
        """Wake up all threads waiting for items on the queued."""
        with self.condition:
            self.condition.notify_all()
