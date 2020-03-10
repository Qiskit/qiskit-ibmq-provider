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

import re
import keyword
from typing import List, Optional, Type, Any
from threading import Condition
from queue import Queue


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


class RefreshQueue(Queue):
    """A queue that replaces the oldest item with the new when full.

    A FIFO queue with a bounded size. Once the queue is full, when new items
    are added, a corresponding number of items are discarded from the
    opposite end.
    """

    def __init__(self, maxsize: int):
        """RefreshQueue constructor.

        Args:
            maxsize: Maximum size of the queue.
        """
        self.condition = Condition()
        # self.queue = Queue(maxsize)
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
            self.condition.notifyAll()
