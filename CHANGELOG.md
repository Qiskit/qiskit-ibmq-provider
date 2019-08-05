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

### Changed

- The `backend.properties()` function now accepts an optional `datetime` 
  parameter. If specified, the function returns the backend properties closest 
  to, but older than, the specified datetime filter (\#277).

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


[UNRELEASED]: https://github.com/Qiskit/qiskit-ibmq-provider/compare/0.3.1...HEAD
[0.3.1]: https://github.com/Qiskit/qiskit-ibmq-provider/compare/0.3.0...0.3.1
[0.3.0]: https://github.com/Qiskit/qiskit-ibmq-provider/compare/0.2.2...0.3.0
[0.2.2]: https://github.com/Qiskit/qiskit-ibmq-provider/compare/0.2.1...0.2.2
[0.2.1]: https://github.com/Qiskit/qiskit-ibmq-provider/compare/0.2.0...0.2.1
[0.2.0]: https://github.com/Qiskit/qiskit-ibmq-provider/compare/0.1.1...0.2.0
[0.1.1]: https://github.com/Qiskit/qiskit-ibmq-provider/compare/0.1...0.1.1
[0.1]: https://github.com/Qiskit/qiskit-ibmq-provider/compare/104d524...0.1

[Keep a Changelog]: http://keepachangelog.com/en/1.0.0/
