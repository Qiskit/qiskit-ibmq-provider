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

"""Session customized for IBM Quantum Experience access."""

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
    """Custom ``urllib3.Retry`` class that performs retry on ``POST`` errors in the force list.

    Retrying of ``POST`` requests are allowed *only* when the status code
    returned is on the ``STATUS_FORCELIST``. While ``POST``
    requests are recommended not to be retried due to not being idempotent,
    the IBM Quantum Experience API guarantees that retrying on specific 5xx errors is safe.
    """

    def is_retry(
            self,
            method: str,
            status_code: int,
            has_retry_after: bool = False
    ) -> bool:
        """Indicate whether the request should be retried.

        Args:
            method: Request method.
            status_code: Status code.
            has_retry_after: Whether retry has been done before.

        Returns:
            ``True`` if the request should be retried, ``False`` otherwise.
        """
        if method.upper() == 'POST' and status_code in self.status_forcelist:
            return True

        return super().is_retry(method, status_code, has_retry_after)


class RetrySession(Session):
    """Custom session with retry and handling of specific parameters.

    This is a child class of ``requests.Session``. It has its own retry
    policy and handles IBM Quantum Experience specific parameters.
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
            base_url: Base URL for the session's requests.
            access_token: Access token.
            retries_total: Number of total retries for the requests.
            retries_connect: Number of connect retries for the requests.
            backoff_factor: Backoff factor between retry attempts.
            verify: Whether to enable SSL verification.
            proxies: Proxy URLs mapped by protocol.
            auth: Authentication handler.
            timeout: Timeout for the requests, in the form of (connection_timeout,
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
        """Set the session retry policy.

        Args:
            retries_total: Number of total retries for the requests.
            retries_connect: Number of connect retries for the requests.
            backoff_factor: Backoff factor between retry attempts.
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
        """Set the session parameters and attributes.

        Args:
            verify: Whether to enable SSL verification.
            proxies: Proxy URLs mapped by protocol.
            auth: Authentication handler.
        """
        client_app_header = CLIENT_APPLICATION

        # Append custom header to the end if specified
        custom_header = os.getenv(CUSTOM_HEADER_ENV_VAR)
        if custom_header:
            client_app_header += "/" + custom_header

        self.headers.update({'X-Qx-Client-Application': client_app_header})
        self.headers['Content-Type'] = 'application/json'

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
        """Construct, prepare, and send a ``Request``.

        If `bare` is not specified, prepend the base URL to the input `url`.
        Timeout value is passed if proxies are not used.

        Args:
            method: Method for the new request (e.g. ``POST``).
            url: URL for the new request.
            bare: If ``True``, do not send IBM Quantum Experience specific information
                (such as access token) in the request or modify the input `url`.
            **kwargs: Additional arguments for the request.

        Returns:
            Response object.

        Raises:
            RequestsApiError: If the request failed.
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
        """Modify the chained exception messages.

        Args:
            exc: Exception whose parent messages are to be modified.
        """
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
