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

"""
==============================================
Runtime (:mod:`qiskit.providers.ibmq.runtime`)
==============================================

.. currentmodule:: qiskit.providers.ibmq.runtime

Modules related to Qiskit Runtime Service.

.. note::

    The Qiskit Runtime service is not available to all providers. To check if your provider
    has access::

        from qiskit import IBMQ

        IBMQ.load_account()
        provider = IBMQ.get_provider(...)

        can_use_runtime = provider.has_service('runtime')

.. note::

    Not all backends support Qiskit Runtime. Refer to documentation in
    `Qiskit-Partners/qiskit-runtime
    <https://github.com/Qiskit-Partners/qiskit-runtime>`_ for more information.

.. caution::

  This package is currently provided in beta form and heavy modifications to
  both functionality and API are likely to occur. Backward compatibility is not
  always guaranteed.

Qiskit Runtime is a new architecture offered by IBM Quantum that
streamlines computations requiring many iterations. These experiments will
execute significantly faster within its improved hybrid quantum/classical process.

The Qiskit Runtime Service allows authorized users to upload their Qiskit quantum programs.
A Qiskit quantum program, also called a runtime program, is a piece of Python
code and its metadata that takes certain inputs, performs
quantum and maybe classical processing, and returns the results. The same or other
authorized users can invoke these quantum programs by simply passing in parameters.

`Qiskit-Partners/qiskit-runtime <https://github.com/Qiskit-Partners/qiskit-runtime>`_
contains detailed tutorials on how to use Qiskit Runtime.


Listing runtime programs
------------------------

To list all available runtime programs::

    from qiskit import IBMQ

    provider = IBMQ.load_account()

    # List all available programs.
    provider.runtime.pprint_programs()

    # Get a single program.
    program = provider.runtime.program('circuit-runner')

    # Print program metadata.
    print(program)

In the example above, ``provider.runtime`` points to the runtime service class
:class:`IBMRuntimeService`, which is the main entry
point for using this service. The example prints the program metadata of all
available runtime programs and of just the ``circuit-runner`` program. A program
metadata consists of the program's ID, name, description, input parameters,
return values, interim results, and other information that helps you to know
more about the program.

Invoking a runtime program
--------------------------

You can use the :meth:`IBMRuntimeService.run` method to invoke a runtime program.
For example::

    from qiskit import IBMQ, QuantumCircuit
    from qiskit.providers.ibmq import RunnerResult


    provider = IBMQ.load_account()
    backend = provider.backend.ibmq_qasm_simulator

    # Create a circuit.
    qc = QuantumCircuit(2, 2)
    qc.h(0)
    qc.cx(0, 1)
    qc.measure_all()

    # Set the "circuit-runner" program parameters
    params = provider.runtime.program(program_id="circuit-runner").parameters()
    params.circuits = qc
    params.measurement_error_mitigation = True

    # Configure backend options
    options = {'backend_name': backend.name()}

    # Execute the circuit using the "circuit-runner" program.
    job = provider.runtime.run(program_id="circuit-runner",
                            options=options,
                            inputs=params)

    # Get runtime job result.
    result = job.result(decoder=RunnerResult)

The example above invokes the ``circuit-runner`` program,
which compiles, executes, and optionally applies measurement error mitigation to
the circuit result.

Runtime Jobs
------------

When you use the :meth:`IBMRuntimeService.run` method to invoke a runtime
program, a
:class:`RuntimeJob` instance is returned. This class has all the basic job
methods, such as :meth:`RuntimeJob.status`, :meth:`RuntimeJob.result`, and
:meth:`RuntimeJob.cancel`. Note that it does not have the same methods as regular
circuit jobs, which are instances of :class:`~qiskit.providers.ibmq.job.IBMQJob`.

Interim results
---------------

Some runtime programs provide interim results that inform you about program
progress. You can choose to stream the interim results when you run the
program by passing in the ``callback`` parameter, or at a later time using
the :meth:`RuntimeJob.stream_results` method. For example::

    from qiskit import IBMQ, QuantumCircuit

    provider = IBMQ.load_account()
    backend = provider.backend.ibmq_qasm_simulator

    def interim_result_callback(job_id, interim_result):
        print(interim_result)

    # Stream interim results as soon as the job starts running.
    job = provider.runtime.run(program_id="circuit-runner",
                               options=options,
                               inputs=program_inputs,
                               callback=interim_result_callback)

Uploading a program
-------------------

.. note::

  Only authorized accounts can upload programs. Having access to the
  runtime service doesn't imply access to upload programs.

Each runtime program has both ``data`` and ``metadata``. Program data is
the Python code to be executed. Program metadata provides usage information,
such as program description, its inputs and outputs, and backend requirements.
A detailed program metadata helps the consumers of the program to know what is
needed to run the program.

Each program data needs to have a ``main(backend, user_messenger, **kwargs)``
method, which serves as the entry point to the program. The ``backend`` parameter
is a :class:`ProgramBackend` instance whose :meth:`ProgramBackend.run` method
can be used to submit circuits. The ``user_messenger`` is a :class:`UserMessenger`
instance whose :meth:`UserMessenger.publish` method can be used to publish interim and
final results.
See `qiskit/providers/ibmq/runtime/program/program_template.py` for a program data
template file.

Each program metadata must include at least the program name, description, and
maximum execution time. You can find description of each metadata field in
the :meth:`IBMRuntimeService.upload_program` method. Instead of passing in
the metadata fields individually, you can pass in a JSON file or a dictionary
to :meth:`IBMRuntimeService.upload_program` via the ``metadata`` parameter.
`qiskit/providers/ibmq/runtime/program/program_metadata_sample.json`
is a sample file of program metadata.

You can use the :meth:`IBMRuntimeService.upload_program` to upload a program.
For example::

    from qiskit import IBMQ

    provider = IBMQ.load_account()
    program_id = provider.runtime.upload_program(
                    data="my_vqe.py",
                    metadata="my_vqe_metadata.json",
                    version="1.2"
                )

In the example above, the file ``my_vqe.py`` contains the program data, and
``my_vqe_metadata.json`` contains the program metadata. An additional
parameter ``version`` is also specified, which takes precedence over any
``version`` value specified in ``my_vqe_metadata.json``.

Method :meth:`IBMRuntimeService.delete_program` allows you to delete a
program.

Files related to writing a runtime program are in the
``qiskit/providers/ibmq/runtime/program`` directory.


Classes
==========================
.. autosummary::
   :toctree: ../stubs/

   IBMRuntimeService
   RuntimeJob
   RuntimeProgram
   UserMessenger
   ProgramBackend
   ResultDecoder
   RuntimeEncoder
   RuntimeDecoder
   ParameterNamespace
"""

from .ibm_runtime_service import IBMRuntimeService
from .runtime_job import RuntimeJob
from .runtime_program import RuntimeProgram, ParameterNamespace
from .program.user_messenger import UserMessenger
from .program.program_backend import ProgramBackend
from .program.result_decoder import ResultDecoder
from .utils import RuntimeEncoder, RuntimeDecoder
