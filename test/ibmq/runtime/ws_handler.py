# This code is part of Qiskit.
#
# (C) Copyright IBM 2021.
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

JOB_ID_PROGRESS_DONE = 'JOB_ID_PROGRESS_DONE'
JOB_ID_ALREADY_DONE = 'JOB_ID_ALREADY_DONE'
JOB_ID_RETRY_SUCCESS = 'JOB_ID_RETRY_SUCCESS'
JOB_ID_RETRY_FAILURE = 'JOB_ID_RETRY_FAILURE'
JOB_PROGRESS_RESULT_COUNT = 5


async def websocket_handler(websocket, path):
    """Entry point for the websocket mock server."""
    request = path.split('/')[-1]
    await websocket.send("ACK")

    if request == JOB_ID_PROGRESS_DONE:
        await handle_job_progress_done(websocket)
    elif request == JOB_ID_ALREADY_DONE:
        await handle_job_already_done(websocket)
    elif request == JOB_ID_RETRY_SUCCESS:
        await handle_token_retry_success(websocket)
    elif request == JOB_ID_RETRY_FAILURE:
        await handle_token_retry_failure(websocket)
    else:
        raise ValueError(f"Unknown request {request}")


async def handle_job_progress_done(websocket):
    """Send a few results then close with 1000."""
    for idx in range(JOB_PROGRESS_RESULT_COUNT):
        await websocket.send(f"foo{idx}")
        await asyncio.sleep(1)
    await websocket.close(code=1000)


async def handle_job_already_done(websocket):
    """Close immediately with 1000."""
    await websocket.close(code=1000)


async def handle_token_retry_success(websocket):
    """Close the socket once and force a retry."""
    if not hasattr(handle_token_retry_success, 'retry_attempt'):
        setattr(handle_token_retry_success, 'retry_attempt', True)
        await handle_token_retry_failure(websocket)
    else:
        await handle_job_progress_done(websocket)


async def handle_token_retry_failure(websocket):
    """Continually close the socket, until both the first attempt and retry fail."""
    await websocket.close(code=1011)
