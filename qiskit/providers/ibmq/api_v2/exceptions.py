# -*- coding: utf-8 -*-

# Copyright 2019, IBM.
#
# This source code is licensed under the Apache License, Version 2.0 found in
# the LICENSE.txt file in the root directory of this source tree.

"""Exceptions related to the IBM Q Api."""
from qiskit.providers.ibmq.api import ApiError as ApiErrorV1


class ApiError(ApiErrorV1):
    def __init__(self, *args, original_exception=None, **kwargs):
        self.original_exception = original_exception
        super().__init__(*args, **kwargs)
