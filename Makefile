# This code is part of Qiskit.
#
# (C) Copyright IBM 2017, 2021.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.


.PHONY: lint style test mypy test1 test2 test3 runtime_integration experiment_integration

lint:
	pylint -rn qiskit/providers/ibmq test
	tools/verify_headers.py qiskit test

mypy:
	mypy --module qiskit.providers.ibmq

style:
	pycodestyle qiskit test

test:
	python -m unittest -v

test1:
	python -m unittest -v test/ibmq/test_ibmq_backend.py test/ibmq/test_account_client.py test/ibmq/test_ibmq_job_states.py test/ibmq/test_tutorials.py test/ibmq/test_basic_server_paths.py test/ibmq/test_ibmq_factory.py test/ibmq/test_proxies.py test/ibmq/test_ibmq_integration.py test/ibmq/test_ibmq_logger.py test/ibmq/test_filter_backends.py test/ibmq/test_registration.py

test2:
	python -m unittest -v test/ibmq/test_ibmq_qasm_simulator.py test/ibmq/test_serialization.py test/ibmq/test_jupyter.py test/ibmq/test_ibmq_jobmanager.py test/ibmq/test_random.py test/ibmq/test_ibmq_provider.py

test3:
	python -m unittest -v test/ibmq/test_ibmq_job_attributes.py test/ibmq/test_ibmq_job.py test/ibmq/websocket/test_websocket.py test/ibmq/websocket/test_websocket_integration.py

runtime_integration:
	python -m unittest -v test/ibmq/runtime/test_runtime_integration.py

experiment_integration:
	python -m unittest -v test/ibmq/experiment/test_experiment_data_integration.py test/ibmq/experiment/test_experiment_server_integration.py