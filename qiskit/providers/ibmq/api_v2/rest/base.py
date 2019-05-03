# -*- coding: utf-8 -*-

# Copyright 2019, IBM.
#
# This source code is licensed under the Apache License, Version 2.0 found in
# the LICENSE.txt file in the root directory of this source tree.

"""REST clients for accessing IBM Q."""


class RestAdaptorBase:

    URL_MAP = {}

    def __init__(self, session, prefix_url=''):
        self.session = session
        self.prefix_url = prefix_url

    def get_url(self, identifier):
        return '{}{}'.format(self.prefix_url, self.URL_MAP[identifier])
