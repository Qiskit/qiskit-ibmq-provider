# Copyright 2018, IBM.
#
# This source code is licensed under the Apache License, Version 2.0 found in
# the LICENSE.txt file in the root directory of this source tree.

.PHONY: lint style test

lint:
	pylint -rn qiskit test

style:
	pycodestyle --max-line-length=100 qiskit test

test:
	python -m unittest
