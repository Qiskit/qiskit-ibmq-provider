# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog].

> **Types of changes:**
>
> - **Added**: for new features.
> - **Changed**: for changes in existing functionality.
> - **Deprecated**: for soon-to-be removed features.
> - **Removed**: for now removed features.
> - **Fixed**: for any bug fixes.
> - **Security**: in case of vulnerabilities.


## [UNRELEASED]

### Added

- A new `IBMQJobManager` class that takes a list of circuits or pulse schedules
  as input, splits them into one or more jobs, and submits the jobs.
  (\#389, \#400, \#407)
- New features to `provider.backends`:
  - it contains the available backends as attributes. A user can now use
    `provider.backends.<tab>` to see a list of backend names, and make
     use of the attributes as regular `IBMQBackend` instances. (\#303)
  - the methods `provider.backends.jobs()` and
    `provider.backends.retrieve_job()` can be used for retrieving
    provider-wide jobs. (\#354)

### Changed

- `IBMQBackend.run()` now accepts an optional `job_name` parameter. If
  specified, the `job_name` is assigned to the job, which can also be used
  as a filter in `IBMQBackend.jobs()`. (\#300, \#384)
- The signature of `IBMQBackend.jobs()` is changed. `db_filter`, which was the 
  4th parameter, is now the 5th parameter. (\#300)
- The `backend.properties()` function now accepts an optional `datetime` 
  parameter. If specified, the function returns the backend properties closest 
  to, but older than, the specified datetime filter. (\#277)
- The `WebsocketClient.get_job_status()` method now accepts two optional 
  parameters: `retries` and `backoff_factor`. (\#341)
- The `IBMQJob` class has been refactored:
  - The `IBMQJob` attributes are now automatically populated based on the
    information contained in the remote API. As a result, the `IBMQJob`
    constructor signature has changed. (\#329)
  - `IBMQJob.submit()` can no longer be called directly, and jobs are expected
    to be submitted via `IBMQBackend.run()`. (\#329)
  - `IBMQJob.error_message()` now gives more information on why a job failed.
     (\#375)
  - `IBMQJob.queue_position()` now accepts an optional `refresh` parameter that
    indicates whether it should query the API for the latest queue position.
    (\#387)
  - The `IBMQJob.result()` function now accepts an optional `partial` parameter.
    If specified, `IBMQJob.result()` will return partial results for jobs with
    experiments that failed. (\#399)
- The Exception hierarchy has been refined with more specialized classes, and
  exception chaining is used in some cases - please inspect the complete
  traceback for more informative failures. (\#395, \#396)
- Some `warnings` have been toned down to `logger.warning` messages. (\#379)

### Removed

- Support for the legacy Quantum Experience and QConsole is fully deprecated.
  Only credentials from the new Quantum Experience can be used. (\#344)
- The circuits functionality has been temporarily removed from the provider. It
  will be reintroduced in future versions. (\#429)


## [0.3.3] - 2019-09-30

### Fixed

- Fixed an issue where proxy parameters were not fully passed to the final
  sessions, leading to incomplete proxy support. (\#353)

## [0.3.2] - 2019-08-20

### Changed

- Pin version of `nest_asyncio` requirement. (\#312)

## [0.3.1] - 2019-07-23

### Changed

- The `backend.jobs()` function now has a default `limit` of 10 results, and
  in the IBM Q Experience v2 will automatically perform several API calls in
  order to retrieve the specified number of jobs, if higher. (\#263)

### Fixed

- `load_accounts` dispatches to `load_account` if v2 credentials are stored,
  allowing for backward compatibility. (\#273)

## [0.3.0] - 2019-07-15

### Fixed

- Fixed Circuits status checks according to latest API changes. (\#95)
- Fixed an authentication issue with the `backend_status` endpoint when using
  the new api. (\#101)

### Changed

- The package defaults to connecting to the IBM Q Experience v2 by default, and
  to using a single token and URL for accessing all the remote capabilities.
  - an `IBMQ.update_account()` added for helping transitioning. (\#209)
  - `qiskit.IBMQ` is no longer a `Provider`: providers for the individual
    projects can be obtained via `IBMQ.get_provider()`. (\#214)
  - the `qiskit.IBMQ` account-management methods have been revised, and act
    on a single account. (\#186)
  - the `qiskit.IBMQ` backend-management methods have been moved to the
    individual `AccountProvider` instances. (\#186, \#212).
- Updated detection of classic vs. new api based on version endpoint. (\#95)
- The `requires_qe_access` decorator, previously in terra, is now included in
  this package. (\#128)
- `IBMQJob.job_id()` now accepts an optional `timeout` parameter, for allowing
  users finer control over the waiting time. (\#238)

### Added

- Added support for pooling job status via websockets. Note this is only
  available when using the new API authentication. (\#100)
- Added support for using object storage when submitting and retrieving
  jobs. Note this is only available when using the new IBM Q Experience
  v2. (\#110)
- Added support for custom qx-client-application request header via the environment
  variable `QE_CUSTOM_CLIENT_APP_HEADER` when using the new IBM Q Experience
  v2. (\#165)
- `backend.properties()` and `backend.defaults()` now accept a `refresh` flag.
  When False, cached data will be returned. (\#224)

### Deprecated

- Support for the legacy IBM Q Experience and Qconsole is on the process of
  being deprecated. They will still be supported during the `0.3.x` versions,
  but we encourage transitioning to the new IBM Q Experience. (\#232)
  - the `IBMQ.load_accounts()` and account-management methods are replaced by
    methods that work on a single token and URL.
  - the `IBMQ.backends()` method has been moved to the provider instances:
    `provider = IBMQ.get_provider(); provider.backends()`.
  - the `IBMQ.get_backend(name)` method has been moved to the provider
    instances: `provider = IBMQ.get_provider(); provider.get_backend(name)`.

## [0.2.2] - 2019-05-07

### Fixed

- Fixed Circuits parameter validation. (\#89)


## [0.2.1] - 2019-05-06

### Fixed

- Improved compatibility with older setuptools versions. (\#85)


## [0.2.0] - 2019-05-06

### Added

- The IBMQProvider supports connecting to the new version of the IBM Q API.
  Please note support for this version is still experimental. (\#78)
- Added support for `Circuits` through the new API. (\#79)

### Fixed

- Fixed incorrect parsing of some API hub URLs. (\#77)
- Fixed noise model handling for remote simulators. (\#84)


## [0.1.1] - 2019-05-01

### Changed

- The backend configurations now return instances of specialized
  `BackendConfiguration` classes (ie. `QasmBackendConfiguration`). (\#74).

### Fixed

- Fixed signature mismatch during `job.cancel()`. (\#73)


## [0.1] - 2019-04-17

### Added

- The connector `get_job()` methods accepts two new parameters for including
  and excluding specific fields from the response. (\#6)
- Added `backend.defauls()` for retrieving the pulse defaults for a backend
  through a new endpoint. (\#33)
- Added `job.properties()` for retrieving the backend properties for a job
  through a new endpoint. (\#35)

### Changed

- The IBMQ Provider has been moved to an individual package outside the Qiskit
  Terra package.
- The exception hierarchy has been revised: the package base exception is
  `IBMQError`, and they have been grouped in `.exception` modules. (\#5)
- Ensured that retrieved jobs come from their appropriate backend. (\#23)
- Job `error_message()` function now summarizes the problems that made the job
  to fail. (\#48)
- `backend.jobs()` no longer emits a warning for pre-qobj jobs. (\#59)

### Removed

- Support for non-qobj format has been removed. (\#26, \#28)


[UNRELEASED]: https://github.com/Qiskit/qiskit-ibmq-provider/compare/0.3.3...HEAD
[0.3.3]: https://github.com/Qiskit/qiskit-ibmq-provider/compare/0.3.2...0.3.3
[0.3.2]: https://github.com/Qiskit/qiskit-ibmq-provider/compare/0.3.1...0.3.2
[0.3.1]: https://github.com/Qiskit/qiskit-ibmq-provider/compare/0.3.0...0.3.1
[0.3.0]: https://github.com/Qiskit/qiskit-ibmq-provider/compare/0.2.2...0.3.0
[0.2.2]: https://github.com/Qiskit/qiskit-ibmq-provider/compare/0.2.1...0.2.2
[0.2.1]: https://github.com/Qiskit/qiskit-ibmq-provider/compare/0.2.0...0.2.1
[0.2.0]: https://github.com/Qiskit/qiskit-ibmq-provider/compare/0.1.1...0.2.0
[0.1.1]: https://github.com/Qiskit/qiskit-ibmq-provider/compare/0.1...0.1.1
[0.1]: https://github.com/Qiskit/qiskit-ibmq-provider/compare/104d524...0.1

[Keep a Changelog]: http://keepachangelog.com/en/1.0.0/
