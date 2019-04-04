
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


`0.1rc3`_
^^^^^^^^^


Added
"""""

- The connector ``get_job()`` methods accepts two new parameters for including
  and excluding specific fields from the response. (#6)
- Added ``backend.defauls()`` for retrieving the pulse defaults for a
  backend through a new endpoint (#33).
- Added ``job.properties()`` for retrieving the backend properties for
  a job through a new endpint (#35).

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



.. _UNRELEASED: https://github.com/Qiskit/qiskit-ibmq-provider/compare/104d524...HEAD
.. _0.1rc3: https://github.com/Qiskit/qiskit-ibmq-provider/compare/104d524...0.1rc3

.. _Keep a Changelog: http://keepachangelog.com/en/1.0.0/
