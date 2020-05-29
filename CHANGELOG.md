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

### Fixed

- `backend.jobs(status='RUNNING')` now returns the correct jobs. (\#669)
- Fixed `setup.py` to match `requirements.txt`. (\#678)  

## [0.7.1] - 2020-05-13

### Fixed

- Fixed an issue where job status was incorrectly shown as `RUNNING` when it
  should be `QUEUED`. (\#663)
- Fixed timestamp formats in `QueueInfo`. (\#668)
- Fixed timestamp formats in `backend.configuration()` and `backend.properties()`
  return values. (\#658)

## [0.7.0] - 2020-04-29

### Added

- A new exception, `IBMQBackendJobLimitError`, is now raised if a job 
  could not be submitted because the limit on active jobs has been reached.
- `IBMQJob` and `ManagedJobSet` both have two new methods `update_name()` and 
  `update_tags()`. They are used to change the name and tags of a job or job set, 
  respectively. (\#590)
- `IBMQFactory.save_account()` and `IBMQFactory.enable_account()` now accept
  the optional parameters `hub`, `group`, `project`, which allow specifying a 
  default provider to save to disk or use, respectively. (\#611)     

### Changed

- `IBMQJob.creation_date()` and `IBMQJob.time_per_step()` now return date time
  information as a datetime object in local time. Also, the parameters 
  `start_datetime` and `end_datetime`, of `IBMQBackendService.jobs()` and 
  `IBMQBackend.jobs()`, can now be specified in local time. (\#622) 

### Fixed

- Fixed an issue where `nest_asyncio.apply()` may raise an exception
  if there is no asyncio loop due to threading. (\#595)

### Removed

- The `done()`, `running()`, and `cancelled()` methods were removed from 
  `IBMQJob`, since they are now a part of `BaseJob`.  
- Marshmallow validation is removed for performance. (\#632)


### Deprecated

- The `from_dict()` and `to_dict()` methods of `IBMQJob` are deprecated and
  will be removed in the next release. (\#632)
  
## [0.6.1] - 2020-04-22

### Fixed

- Increased timeout value to allow large Qobj to be uploaded. (\#626)
- Added a JSON decoder to convert lists in Qobj to complex. (\#631) 

## [0.6.0] - 2020-03-26

### Added

- There are three new exceptions: `VisualizationError`, `VisualizationValueError`,
  and `VisualizationTypeError`. These are now used in the visualization modules when
  an exception is raised. Also, `IBMQBackend.status()` now raises a 
  `IBMQBackendApiProtocolError` exception, instead of a general `LookupError`, 
  if there was an issue with validating the status. (\#572)
- You can now set the logging level and specify a log file using the environment 
  variables `QSIKIT_IBMQ_PROVIDER_LOG_LEVEL` and `QISKIT_IBMQ_PROVIDER_LOG_FILE`, 
  respectively. Note that the name of the logger is `qiskit.providers.ibmq`. (\#579)
- `IBMQJob` now has a new method `scheduling_mode()` that returns the scheduling
  mode the job is in. (\#593)
- IQX-related tutorials that used to be in `qiskit-iqx-tutorials` are now in 
  `qiskit-ibmq-provider`. (\#603)

### Changed

- `IBMQBackend.jobs()` now accepts a new boolean parameter `descending`,
  which can be used to indicate whether the jobs should be returned in
  descending or ascending order. (\#533) 
- `IBMQJobManager` now looks at the job limit and waits for old jobs
  to finish before submitting new ones if the limit has been reached. (\#533)

## [0.5.0] - 2020-02-26

### Added

- Some of the visualization and Jupyter tools, including gate/error map and
  backend information, have been moved 
  from `qiskit-terra` to `qiskit-ibmq-provider`. In addition, you can now 
  use `%iqx_dashboard` to get a dashboard that provides both job and 
  backend information. (\#535) (\#541)

### Changed

- JSON schema validation is no longer run by default on Qobj objects passed
  to `IBMQBackend.run()`. This significantly speeds up the execution of the
  `run` method and the API server will return 400 if the Qobj is invalid. If
  you would like to still run the validation you can set the `validate_qobj`
  kwarg to `True` which will enable the JSON schema validation. (\#554)

## [0.4.6] - 2020-02-05

### Added

- `IBMQJob` now has a new method `wait_for_final_state()` that blocks
  until the job finishes. One of its parameters is a callback function 
  that it will invoke after every query to provide feedback. (\#529)
- `IBMQBackend` now has a new method `active_jobs()`. The method returns the 
  jobs submitted to a backend that are currently in an unfinished status.
  Note the unfinished jobs returned for the backend are given for a specific 
  provider (i.e. a specific backend with a specific provider). (\#521)
- `QueueInfo` (returned by `IBMQJob.queue_info()`) now has a new method: 
  `format()`. The method returns a formatted string of the queue information.
  (\#515)
- `IBMQJob` now has three new methods: `done()`, `running()`, and
  `cancelled()`. The methods are used to indicate the job status. (\#494)  
- `backend.run()` now accepts an optional `job_tags` parameter. If
  specified, the `job_tags` are assigned to the job, which can also be used
  as a filter in `backend.jobs()`. (\#511)
- `IBMQBackend` now has two new methods: `job_limit()` and 
  `remaining_job_counts()`. `job_limit()` returns the job limit for a 
  backend, which includes the current number of active jobs you have on 
  the backend and the the maximum number of active jobs you can have on 
  it. `remaining_job_counts()` returns the number of remaining jobs that 
  could be submitted to the backend before the maximum limit on active
  jobs is reached. Note the job limit for a backend is given for a specific 
  provider (i.e. a specific backend with a specific provider). (\#513)
- `IBMQJobManager` now has a new method `retrieve_job_set()` that allows
  you to retrieve a previously submitted job set using the job set ID.
  A job set ID can be retrieved using the new `job_set.job_set_id()` 
  method. (\#514)

### Changed

- The Exception hierarchy has been refined with more specialized classes. 
  You can, however, continue to catch their parent exceptions (such 
  as `IBMQAccountError`). Also, the exception class `IBMQApiUrlError` 
  has been replaced by `IBMQAccountCredentialsInvalidUrl` and 
  `IBMQAccountCredentialsInvalidToken`. (\#480)

### Deprecated

- The use of proxy urls without a protocol (e.g. `http://`) is deprecated
  due to recent Python changes. (\#538)


## [0.4.5] - 2019-12-18

### Added

- `IBMQJob` now has a new `queue_info()` method that returns queue 
  information, such as queue position, estimated start/end time, and 
  priority levels for the job. (\#467)  
- Python 3.8 is now supported in qiskit-ibmq-provider. (\#445)

## [0.4.4] - 2019-12-09

### Added

- `IBMQJob.result()` now accepts an optional `refresh` parameter. If 
  `refresh=True` is specified, the function re-queries the api for the 
  results, rather than returning those cached. (\#469)
- `POST` network request are now retried if the status code is among specific
  safe codes. In the case of the request failing during job submission, more
  information is now displayed in the `INFO` and `DEBUG` log levels. (\#475)

### Deprecated

- Python 3.5 support in qiskit-ibmq-provider is deprecated. Support will be
  removed on the upstream python community's end of life date for the version,
  which is 09/13/2020.  (\#445)
  

## [0.4.3] - 2019-11-21

### Fixed

- Fixed an issue where `IBMQJob.error_message()` may raise an exception
  if the job fails before execution. (\#458)

## [0.4.2] - 2019-11-18

### Fixed

- Fixed `IBMQBackendService.jobs()` to correctly return jobs when
  both `start_datetime` and `end_datetime` are specified. Now, when the 
  two parameters are specified, the function will return the jobs after 
  (greater than or equal to) and before (less than or equal to) the 
  two given datetimes. (\#452)

## [0.4.1] - 2019-11-14

### Fixed

- Fixed `job.creation_date()` return string format to be the same as that of 
  release 0.3. (\#447)

### Changed

- `IBMBackend.jobs()` and `IBMQBackendService.jobs()` now accept the 
  optional parameters `start_datetime` and `end_datetime`. If one is 
  specified, it is used to find jobs whose creation date is after 
  (greater than) or before (less than) the given the date/time, 
  respectively. If both are specified, they are used to find jobs 
  whose creation date is between the two dates. (\#443)

## [0.4.0] - 2019-11-12

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
- `IBMQBackend.run()` now accepts an optional `job_share_level`
  parameter. If specified, the job could be shared with other users at the
  global, hub, group, project, or none level. (\#414)
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


[UNRELEASED]: https://github.com/Qiskit/qiskit-ibmq-provider/compare/0.7.1...HEAD
[0.7.1]: https://github.com/Qiskit/qiskit-ibmq-provider/compare/0.7.0...0.7.1
[0.7.0]: https://github.com/Qiskit/qiskit-ibmq-provider/compare/0.6.1...0.7.0
[0.6.1]: https://github.com/Qiskit/qiskit-ibmq-provider/compare/0.6.0...0.6.1
[0.6.0]: https://github.com/Qiskit/qiskit-ibmq-provider/compare/0.5.0...0.6.0
[0.5.0]: https://github.com/Qiskit/qiskit-ibmq-provider/compare/0.4.6...0.5.0
[0.4.6]: https://github.com/Qiskit/qiskit-ibmq-provider/compare/0.4.5...0.4.6
[0.4.5]: https://github.com/Qiskit/qiskit-ibmq-provider/compare/0.4.4...0.4.5
[0.4.4]: https://github.com/Qiskit/qiskit-ibmq-provider/compare/0.4.3...0.4.4
[0.4.3]: https://github.com/Qiskit/qiskit-ibmq-provider/compare/0.4.2...0.4.3
[0.4.2]: https://github.com/Qiskit/qiskit-ibmq-provider/compare/0.4.1...0.4.2
[0.4.1]: https://github.com/Qiskit/qiskit-ibmq-provider/compare/0.4.0...0.4.1
[0.4.0]: https://github.com/Qiskit/qiskit-ibmq-provider/compare/0.3.3...0.4.0
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
