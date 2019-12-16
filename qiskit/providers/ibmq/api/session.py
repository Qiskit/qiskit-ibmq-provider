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
from typing import Dict, Optional, Any, Tuple, Union
from requests import Session, RequestException, Response
from requests.adapters import HTTPAdapter
from requests.auth import AuthBase
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


class PostForcelistRetry(Retry):
    """Custom Retry that performs retry on POST errors in the forcelist.

    Custom `urllib3.Retry` that allows retrying in `POST` requests *only* when
    the status code returned belongs to the `STATUS_FORCELIST`. While `POST`
    requests are recommended not to be retried due to not being idempotent,
    the IBM Q API guarantees that retrying on specific 5xx errors is safe.
    """

    def is_retry(
            self,
            method: str,
            status_code: int,
            has_retry_after: bool = False
    ) -> bool:
        if method.upper() == 'POST' and status_code in self.status_forcelist:
            return True

        return super().is_retry(method, status_code, has_retry_after)


class RetrySession(Session):
    """Session with retry and handling of IBM Q parameters.

    Custom session for use with IBM Q, that includes a retry mechanism based
    on urllib3 and handling of specific parameters based on
    ``requests.Session``.
    """

    def __init__(
            self,
            base_url: str,
            access_token: Optional[str] = None,
            retries_total: int = 5,
            retries_connect: int = 3,
            backoff_factor: float = 0.5,
            verify: bool = True,
            proxies: Optional[Dict[str, str]] = None,
            auth: Optional[AuthBase] = None,
            timeout: Tuple[float, Union[float, None]] = (5.0, None)
    ) -> None:
        """RetrySession constructor.

        Args:
            base_url: base URL for the session's requests.
            access_token: access token.
            retries_total: number of total retries for the requests.
            retries_connect: number of connect retries for the requests.
            backoff_factor: backoff factor between retry attempts.
            verify: enable SSL verification.
            proxies: proxy URLs mapped by protocol.
            auth: authentication handler.
            timeout: timeout for the requests, in the form (connection_timeout,
                total_timeout).
        """
        super().__init__()

        self.base_url = base_url
        self._access_token = access_token
        self.access_token = access_token

        self._initialize_retry(retries_total, retries_connect, backoff_factor)
        self._initialize_session_parameters(verify, proxies or {}, auth)
        self._timeout = timeout

    def __del__(self) -> None:
        """RetrySession destructor. Closes the session."""
        self.close()

    @property
    def access_token(self) -> Optional[str]:
        """Return the session access token."""
        return self._access_token

    @access_token.setter
    def access_token(self, value: Optional[str]) -> None:
        """Set the session access token."""
        self._access_token = value
        if value:
            self.headers.update({'X-Access-Token': value})  # type: ignore[attr-defined]
        else:
            self.headers.pop('X-Access-Token', None)  # type: ignore[attr-defined]

    def _initialize_retry(
            self,
            retries_total: int,
            retries_connect: int,
            backoff_factor: float
    ) -> None:
        """Set the Session retry policy.

        Args:
            retries_total: number of total retries for the requests.
            retries_connect: number of connect retries for the requests.
            backoff_factor: backoff factor between retry attempts.
        """
        retry = PostForcelistRetry(
            total=retries_total,
            connect=retries_connect,
            backoff_factor=backoff_factor,
            status_forcelist=STATUS_FORCELIST,
        )

        retry_adapter = HTTPAdapter(max_retries=retry)
        self.mount('http://', retry_adapter)
        self.mount('https://', retry_adapter)

    def _initialize_session_parameters(
            self,
            verify: bool,
            proxies: Dict[str, str],
            auth: Optional[AuthBase] = None
    ) -> None:
        """Set the Session parameters and attributes.

        Args:
            verify: enable SSL verification.
            proxies: proxy URLs mapped by protocol.
            auth: authentication handler.
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

    def request(  # type: ignore[override]
            self,
            method: str,
            url: str,
            bare: bool = False,
            **kwargs: Any
    ) -> Response:
        """Constructs a Request, prepending the base url.

        Args:
            method: method for the new `Request` object.
            url: URL for the new `Request` object.
            bare: if `True`, do not send IBM Q specific information
                (access token) in the request or modify the `url`.
            kwargs: additional arguments for the request.

        Returns:
            Response object.

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

        # Add a timeout to the connection for non-proxy connections.
        if not self.proxies:
            kwargs.update({'timeout': self._timeout})

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
                # Modify the original message on the chained exceptions.
                self._modify_chained_exception_messages(ex)

            raise RequestsApiError(message) from ex

        return response

    def _modify_chained_exception_messages(self, exc: BaseException) -> None:
        if exc.__cause__:
            self._modify_chained_exception_messages(exc.__cause__)
        elif exc.__context__:
            self._modify_chained_exception_messages(exc.__context__)

        # Loop through args, attempt to replace access token if string.
        modified_args = []
        for arg in exc.args:
            exc_message = arg
            if isinstance(exc_message, str):
                exc_message = exc_message.replace(self.access_token, '...')
            modified_args.append(exc_message)
        exc.args = tuple(modified_args)
