# -*- coding: utf-8 -*-

# This code is part of Qiskit.
#
# (C) Copyright IBM 2017, 2018.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Websocket server for testing purposes."""

import asyncio
import json

from qiskit.providers.ibmq.api_v2.clients.websocket import WebsocketMessage


TOKEN_JOB_COMPLETED = 'token_job_completed'
TOKEN_JOB_TRANSITION = 'token_job_transition'
TOKEN_TIMEOUT = 'token_timeout'
TOKEN_WRONG_FORMAT = 'token_wrong_format'


@asyncio.coroutine
def websocket_handler(websocket, path):
    """Entry point for the websocket mock server."""
    # pylint: disable=unused-argument
    # Receive the authentication message.
    msg_in = yield from websocket.recv()
    auth_message = json.loads(msg_in)

    # Check for valid access tokens.
    token = auth_message['data']
    if token in (TOKEN_JOB_COMPLETED,
                 TOKEN_JOB_TRANSITION,
                 TOKEN_TIMEOUT,
                 TOKEN_WRONG_FORMAT):
        msg_out = json.dumps({'type': 'authenticated'})
        yield from websocket.send(msg_out.encode('utf8'))
    else:
        # Close the connection.
        yield from websocket.close()

    # Depending on the access token, perform different actions:
    if token == TOKEN_JOB_COMPLETED:
        yield from handle_token_job_completed(websocket)
    elif token == TOKEN_JOB_TRANSITION:
        yield from handle_token_job_transition(websocket)
    elif token == TOKEN_TIMEOUT:
        yield from handle_token_timeout(websocket)
    elif token == TOKEN_WRONG_FORMAT:
        yield from handle_token_wrong_format(websocket)


@asyncio.coroutine
def handle_token_job_completed(websocket):
    """Return a final job status, and close with 4002."""
    msg_out = WebsocketMessage(type_='job-status',
                               data={'status': 'COMPLETED'})

    yield from websocket.send(msg_out.as_json().encode('utf8'))
    yield from websocket.close(code=4002)


@asyncio.coroutine
def handle_token_job_transition(websocket):
    """Send several job status, and close with 4002."""
    msg_out = WebsocketMessage(type_='job-status',
                               data={'status': 'RUNNING'})
    yield from websocket.send(msg_out.as_json().encode('utf8'))

    yield from asyncio.sleep(1)
    msg_out = WebsocketMessage(type_='job-status',
                               data={'status': 'COMPLETED'})
    yield from websocket.send(msg_out.as_json().encode('utf8'))

    yield from websocket.close(code=4002)


@asyncio.coroutine
def handle_token_timeout(websocket):
    """Close the socket after 10 seconds, without replying."""
    yield from asyncio.sleep(10)
    yield from websocket.close()


@asyncio.coroutine
def handle_token_wrong_format(websocket):
    """Return a status in an invalid format."""
    yield from websocket.send('INVALID'.encode('utf8'))
    yield from websocket.close()
