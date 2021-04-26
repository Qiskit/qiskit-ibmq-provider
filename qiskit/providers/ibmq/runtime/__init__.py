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
======================================================
Runtime Service (:mod:`qiskit.providers.ibmq.runtime`)
======================================================

.. currentmodule:: qiskit.providers.ibmq.runtime

Modules related to IBM Quantum Runtime Service.

.. caution::

  This package is currently provided in beta form and heavy modifications to
  both functionality and API are likely to occur.

.. note::

  The runtime service is not available to all accounts.

The IBM Quantum Runtime Service allows authorized users to upload their quantum programs
that can be invoked by others. A quantum program is a piece of code that takes
certain inputs, performs quantum and classical processing, and returns the
results. For example, user A can upload a VQE quantum program that takes a Hamiltonian
and an optimizer as inputs and returns the minimum eigensolver result. User B
can then invoke this program, passing in the inputs and obtaining the results,
with minimal code.

These quantum programs, sometimes called runtime programs, run in a special
runtime environment that is separate from normal circuit job execution and has
special performance advantages.

Listing runtime programs
------------------------

To list all available runtime programs::

    from qiskit import IBMQ

    provider = IBMQ.load_account()

    # List all available programs.
    provider.runtime.pprint_programs()

    # Get a single program.
    program = provider.runtime.program('circuit-runner')

    # Print program definition.
    print(program)

In the example above, ``provider.runtime`` points to the runtime service class
:class:`~qiskit.providers.ibmq.runtime.IBMRuntimeService`, which is the main entry
point for using this service. The example prints the program definitions of all
available runtime programs and of just the ``circuit-runner`` program. A program
definition consists of a program's ID, name, description, input parameters,
return values, interim results, and other information that helps you to know
more about the program.

Invoking a runtime program
--------------------------

You can use the :meth:`IBMRuntimeService.run` method to invoke a runtime program.
For example::

    from qiskit import IBMQ, QuantumCircuit

    provider = IBMQ.load_account()
    backend = provider.backend.ibmq_qasm_simulator

    # Create a circuit.
    qc = QuantumCircuit(2, 2)
    qc.h(0)
    qc.cx(0, 1)
    qc.measure_all()

    # Execute the circuit using the "circuit-runner" program.
    runtime_inputs = {'circuits': circuit, 'measurement_error_mitigation': True}
    options = {'backend_name': backend.name()}
    job = provider.runtime.run(program_id="circuit-runner",
                               options=options,
                               inputs=runtime_inputs)

    # Get runtime job result.
    result = job.result()

The example above invokes the ``circuit-runner`` program,
which compile, executes, and optionally applies measurement error mitigation to
the circuit result.

Runtime Job
-----------

When you use the :meth:`IBMRuntimeService.run` method to invoke a runtime
program, a
:class:`RuntimeJob` instance is returned. This class has all the basic job
methods, such as :meth:`RuntimeJob.status`, :meth:`RuntimeJob.result`, and
:meth:`RuntimeJob.cancel`. Note that it does not have the same methods as regular
circuit jobs, which are instances of :class:`~qiskit.providers.ibmq.job.IBMQJob`.

Interim results
---------------

Some runtime programs provide interim results that inform you about program
progress. You can choose to stream the interim results when you invoke the
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
                               inputs=runtime_inputs,
                               callback=interim_result_callback)

Uploading a program
-------------------


TODO: Add tutorial reference

Classes
==========================
.. autosummary::
   :toctree: ../stubs/

   IBMRuntimeService
   RuntimeJob
   RuntimeProgram
   UserMessenger
   ProgramBackend
"""

from .ibm_runtime_service import IBMRuntimeService
from .runtime_job import RuntimeJob
from .runtime_program import RuntimeProgram
from .program.user_messenger import UserMessenger
from .program.program_backend import ProgramBackend
