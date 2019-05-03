# -*- coding: utf-8 -*-

# Copyright 2018, IBM.
#
# This source code is licensed under the Apache License, Version 2.0 found in
# the LICENSE.txt file in the root directory of this source tree.

"""Session customized for IBM Q access."""

from requests import Session, RequestException
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .exceptions import ApiError


STATUS_FORCELIST = (
    500,  # Internal Server Error
    502,  # Bad Gateway
    503,  # Service Unavailable
    504,  # Gateway Timeout
)
CLIENT_APPLICATION = 'qiskit-api-py'


class RetrySession(Session):
    """Session with retry and handling of IBM Q parameters."""

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
        self.headers.update({'X-Qx-Client-Application': CLIENT_APPLICATION})

        self.auth = auth
        self.proxies = proxies or {}
        self.verify = verify

    def request(self, method, url, **kwargs):
        """Constructs a Request, prepending the base url."""
        # pylint: disable=arguments-differ
        full_url = self.base_url + url

        try:
            response = super().request(method, full_url, **kwargs)
            response.raise_for_status()
        except RequestException as ex:
            # Wrap the requests exceptions into a IBM Q custom one, for
            # compatibility.
            message = str(ex).replace(self.access_token, '[redacted]')

            raise ApiError(message,
                           original_exception=ex)

        return response
