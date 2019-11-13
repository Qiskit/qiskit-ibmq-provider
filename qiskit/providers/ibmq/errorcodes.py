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

"""Error code for the IBMQ module."""

import enum


class IBMQErrorCodes(enum.Enum):
    """Error code for the IBMQ module."""

    # 01xx: credentials errors
    GENERIC_CREDENTIALS_ERROR = '0101'
    LICENSE_ERROR = '0102'
    CREDENTIALS_NOT_FOUND = '0103'
    INVALID_CREDENTIALS_FORMAT = '0104'
    INVALID_URL = '0105'
    INVALID_TOKEN = '0106'
    PROVIDER_MATCH_ERROR = '0107'

    # 02xx: network errors
    GENERIC_NETWORK_ERROR = '0201'
    REQUEST_TIMEOUT = '0202'

    # 03xx: job service errors
    GENERIC_JOB_ERROR = '0301'
    JOB_FINISHED_IN_ERROR = '0303'

    # 04xx: backend service errors
    GENERIC_BACKEND_ERROR = '0401'
    BACKEND_NOT_AVAILABLE = '0402'

    # 06xx: api error
    GENERIC_API_ERROR = '0601'
    API_PROTOCOL_ERROR = '0602'
    API_REQUEST_ERROR = '0603'
    API_AUTHENTICATION_ERROR = '0604'

    # 09xx: generic errors
    GENERIC_ERROR = '0901'
    INVALID_STATE = '0902'
