# -*- coding: utf-8 -*-

# This code is part of Qiskit.
#
# (C) Copyright IBM 2018, 2019.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Session customized for IBM Q Experience access."""

import os
from requests import Session, RequestException
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .exceptions import RequestsApiError
from ..version import __version__ as ibmq_provider_version

STATUS_FORCELIST = (
    502,  # Bad Gateway
    503,  # Service Unavailable
    504,  # Gateway Timeout
)
CLIENT_APPLICATION = 'ibmqprovider/' + ibmq_provider_version
CUSTOM_HEADER_ENV_VAR = 'QE_CUSTOM_CLIENT_APP_HEADER'


class RetrySession(Session):
    """Session with retry and handling of IBM Q parameters.

    Custom session for use with IBM Q, that includes a retry mechanism based
    on urllib3 and handling of specific parameters based on
    ``requests.Session``.
    """

    def __init__(self, base_url, access_token=None,
                 retries=5, backoff_factor=0.5,
                 verify=True, proxies=None, auth=None):
        """RetrySession constructor.

        Args:
            base_url (str): base URL for the session's requests.
            access_token (str): access token.
            retries (int): number of retries for the requests.
            backoff_factor (float): backoff factor between retry attempts.
            verify (bool): enable SSL verification.
            proxies (dict): proxy URLs mapped by protocol.
            auth (AuthBase): authentication handler.
        """
        super().__init__()

        self.base_url = base_url
        self._access_token = access_token
        self.access_token = access_token

        self._initialize_retry(retries, backoff_factor)
        self._initialize_session_parameters(verify, proxies or {}, auth)

    def __del__(self):
        """RetrySession destructor. Closes the session."""
        self.close()

    @property
    def access_token(self):
        """Return the session access token."""
        return self._access_token

    @access_token.setter
    def access_token(self, value):
        """Set the session access token."""
        self._access_token = value
        if value:
            self.params.update({'access_token': value})
        else:
            self.params.pop('access_token', None)

    def _initialize_retry(self, retries, backoff_factor):
        """Set the Session retry policy.

        Args:
            retries (int): number of retries for the requests.
            backoff_factor (float): backoff factor between retry attempts.
        """
        retry = Retry(
            total=retries,
            backoff_factor=backoff_factor,
            status_forcelist=STATUS_FORCELIST,
        )

        retry_adapter = HTTPAdapter(max_retries=retry)
        self.mount('http://', retry_adapter)
        self.mount('https://', retry_adapter)

    def _initialize_session_parameters(self, verify, proxies, auth):
        """Set the Session parameters and attributes.

        Args:
            verify (bool): enable SSL verification.
            proxies (dict): proxy URLs mapped by protocol.
            auth (AuthBase): authentication handler.
        """
        client_app_header = CLIENT_APPLICATION

        # Append custom header to the end if specified
        custom_header = os.getenv(CUSTOM_HEADER_ENV_VAR)
        if custom_header:
            client_app_header += "/" + custom_header

        self.headers.update({'X-Qx-Client-Application': client_app_header})

        self.auth = auth
        self.proxies = proxies or {}
        self.verify = verify

    def request(self, method, url, bare=False, **kwargs):
        """Constructs a Request, prepending the base url.

        Args:
            method (string): method for the new `Request` object.
            url (string): URL for the new `Request` object.
            bare (bool): if `True`, do not send IBM Q specific information
                (access token) in the request or modify the `url`.
            kwargs (dict): additional arguments for the request.

        Returns:
            Request: Request object.

        Raises:
            RequestsApiError: if the request failed.
        """
        # pylint: disable=arguments-differ
        if bare:
            final_url = url
            # Explicitly pass `None` as the `access_token` param, disabling it.
            params = kwargs.get('params', {})
            params.update({'access_token': None})
            kwargs.update({'params': params})
        else:
            final_url = self.base_url + url

        try:
            response = super().request(method, final_url, **kwargs)
            response.raise_for_status()
        except RequestException as ex:
            # Wrap the requests exceptions into a IBM Q custom one, for
            # compatibility.
            message = str(ex)
            if ex.response is not None:
                try:
                    error_json = ex.response.json()['error']
                    message += ". {}, Error code: {}.".format(
                        error_json['message'], error_json['code'])
                except (ValueError, KeyError):
                    # the response did not contain the expected json.
                    pass

            if self.access_token:
                message = message.replace(self.access_token, '...')

            raise RequestsApiError(ex, message) from None

        return response
