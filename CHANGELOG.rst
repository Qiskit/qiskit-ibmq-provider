
Changelog
---------

All notable changes to this project will be documented in this file.

The format is based on `Keep a Changelog`_.

  **Types of changes:**

  - **Added**: for new features.
  - **Changed**: for changes in existing functionality.
  - **Deprecated**: for soon-to-be removed features.
  - **Removed**: for now removed features.
  - **Fixed**: for any bug fixes.
  - **Security**: in case of vulnerabilities.


`UNRELEASED`_
^^^^^^^^^^^^^

Fixed
"""""

- Fixed Qcircuit status checks according to latest API changes. (#95)
- Fixed an authentication issue with the ``backend_status`` endpoint when
  using the new api. (#101).

Changed
"""""""

- Updated detection of classic vs. new api based on version endpoint. (#95)

Added
"""""

- Added support for pooling job status via websockets. Note this is only
  available when using the new API authentication. (#100)
- Added support for using object storage when submitting and retrieving
  jobs. (#110)


`0.2.2`_ - 2019-05-07
^^^^^^^^^^^^^^^^^^^^^

Fixed
"""""

- Fixed Circuits parameter validation (#89).


`0.2.1`_ - 2019-05-06
^^^^^^^^^^^^^^^^^^^^^

Fixed
"""""

- Improved compatibility with older setuptools versions. (#85)


`0.2.0`_ - 2019-05-06
^^^^^^^^^^^^^^^^^^^^^

Added
"""""

- The IBMQProvider supports connecting to the new version of the IBM Q API.
  Please note support for this version is still experimental. (#78)
- Added support for ``Circuits`` through the new API. (#79).

Fixed
"""""

- Fixed incorrect parsing of some API hub URLs (#77).
- Fixed noise model handling for remote simulators (#84).


`0.1.1`_ - 2019-05-01
^^^^^^^^^^^^^^^^^^^^^

Changed
"""""""

- The backend configurations now return instances of specialized
  ``BackendConfiguration`` classes (ie. ``QasmBackendConfiguration``). (#74).

Fixed
"""""

- Fixed signature mismatch during ``job.cancel()``. (#73)


`0.1`_ - 2019-04-17
^^^^^^^^^^^^^^^^^^^


Added
"""""

- The connector ``get_job()`` methods accepts two new parameters for including
  and excluding specific fields from the response. (#6)
- Added ``backend.defauls()`` for retrieving the pulse defaults for a
  backend through a new endpoint (#33).
- Added ``job.properties()`` for retrieving the backend properties for
  a job through a new endpoint (#35).

Changed
"""""""

- The IBMQ Provider has been moved to an individual package outside the
  Qiskit Terra package.
- The exception hierarchy has been revised: the package base exception is
  ``IBMQError``, and they have been grouped in ``.exception`` modules. (#5)
- Ensured that retrieved jobs come from their appropriate backend (#23)
- Job ``error_message()`` function now summarizes the problems that made the
  job to fail. (#48)
- ``backend.jobs()`` no longer emits a warning for pre-qobj jobs. (#59)

Removed
"""""""

- Support for non-qobj format has been removed. (#26, #28)



.. _UNRELEASED: https://github.com/Qiskit/qiskit-ibmq-provider/compare/0.2.2...HEAD
.. _0.2.2: https://github.com/Qiskit/qiskit-ibmq-provider/compare/0.2.1...0.2.2
.. _0.2.1: https://github.com/Qiskit/qiskit-ibmq-provider/compare/0.2.0...0.2.1
.. _0.2.0: https://github.com/Qiskit/qiskit-ibmq-provider/compare/0.1.1...0.2.0
.. _0.1.1: https://github.com/Qiskit/qiskit-ibmq-provider/compare/0.1...0.1.1
.. _0.1: https://github.com/Qiskit/qiskit-ibmq-provider/compare/104d524...0.1

.. _Keep a Changelog: http://keepachangelog.com/en/1.0.0/
