# -*- coding: utf-8 -*-

# Copyright 2019, IBM.
#
# This source code is licensed under the Apache License, Version 2.0 found in
# the LICENSE.txt file in the root directory of this source tree.

"""Utils for REST adaptors for the IBM Q Api version 2."""

import json
from functools import wraps


def build_url_filter(excluded_fields, included_fields):
    """Return a URL filter based on included and excluded fields."""
    excluded_fields = excluded_fields or []
    included_fields = included_fields or []
    fields_bool = {}

    # Build a map of fields to bool.
    for field_ in excluded_fields:
        fields_bool[field_] = False
    for field_ in included_fields:
        fields_bool[field_] = True

    if 'properties' in fields_bool:
        fields_bool['calibration'] = fields_bool.pop('properties')

    if fields_bool:
        return '&filter=' + json.dumps({'fields': fields_bool})
    return ''


def with_url(url_string):
    def _outer_wrapper(func):
        @wraps(func)
        def _wrapper(self, *args, **kwargs):
            kwargs.update({'url': url_string})
            return func(self, *args, **kwargs)
        return _wrapper
    return _outer_wrapper
