# -*- coding: utf-8 -*-

# Copyright 2018, IBM.
#
# This source code is licensed under the Apache License, Version 2.0 found in
# the LICENSE.txt file in the root directory of this source tree.

"""Exception for the Credentials module."""

from ..exceptions import IBMQError


class CredentialsError(IBMQError):
    """Base class for errors raised during credential management."""
    pass
