Contributing
============

First read the overall project contributing guidelines. These are all
included in the qiskit documentation:

https://qiskit.org/documentation/contributing_to_qiskit.html


Contributing Qiskit IBMQ Provider
---------------------------

In addition to the general guidelines there are specific details for
contributing to the IBMQ Provider, these are documented below.

### Pull request checklist

When submitting a pull request and you feel it is ready for review,
please ensure that:

1. The code follows the code style of the project and successfully
   passes the tests. For convenience, you can execute `tox` locally,
   which will run these checks and report any issues.
2. The documentation has been updated accordingly. In particular, if a
   function or class has been modified during the PR, please update the
   *docstring* accordingly.
3. If it makes sense for your change that you have added new tests that
   cover the changes.
4. Ensure that if your change has an end user facing impact (new feature,
   deprecation, removal etc) that you have added a reno release note for that
   change and that the PR is tagged for the changelog.

### Changelog generation

The changelog is automatically generated as part of the release process
automation. This works through a combination of the git log and the pull
request. When a release is tagged and pushed to github the release automation
bot looks at all commit messages from the git log for the release. It takes the
PR numbers from the git log (assuming a squash merge) and checks if that PR had
a `Changelog:` label on it. If there is a label it will add the git commit
message summary line from the git log for the release to the changelog.

If there are multiple `Changelog:` tags on a PR the git commit message summary
line from the git log will be used for each changelog category tagged.

The current categories for each label are as follows:

| PR Label               | Changelog Category |
| -----------------------|--------------------|
| Changelog: Deprecation | Deprecated         |
| Changelog: New Feature | Added              |
| Changelog: API Change  | Changed            |
| Changelog: Removal     | Removed            |
| Changelog: Bugfix      | Fixed              |

### Release Notes

When making any end user facing changes in a contribution we have to make sure
we document that when we release a new version of qiskit-ibmq-provider. The
expectation is that if your code contribution has user facing changes that you
will write the release documentation for these changes. This documentation must
explain what was changed, why it was changed, and how users can either use or
adapt to the change. The idea behind release documentation is that when a naive
user with limited internal knowledege of the project is upgrading from the
previous release to the new one, they should be able to read the release notes,
understand if they need to update their program which uses qiskit, and how they
would go about doing that. It ideally should explain why they need to make
this change too, to provide the necessary context.

To make sure we don't forget a release note or if the details of user facing
changes over a release cycle we require that all user facing changes include
documentation at the same time as the code. To accomplish this we use the
[reno](https://docs.openstack.org/reno/latest/) tool which enables a git based
workflow for writing and compiling release notes.

#### Adding a new release note

Making a new release note is quite straightforward. Ensure that you have reno
installed with::

    pip install -U reno

Once you have reno installed you can make a new release note by running in
your local repository checkout's root::

    reno new short-description-string

where short-description-string is a brief string (with no spaces) that describes
what's in the release note. This will become the prefix for the release note
file. Once that is run it will create a new yaml file in releasenotes/notes.
Then open that yaml file in a text editor and write the release note. The basic
structure of a release note is restructured text in yaml lists under category
keys. You add individual items under each category and they will be grouped
automatically by release when the release notes are compiled. A single file
can have as many entries in it as needed, but to avoid potential conflicts
you'll want to create a new file for each pull request that has user facing
changes. When you open the newly created file it will be a full template of
the different categories with a description of a category as a single entry
in each category. You'll want to delete all the sections you aren't using and
update the contents for those you are. For example, the end result should
look something like::

```yaml
features:
  - |
    Introduced a new feature foo, that adds support for doing something to
    ``QuantumCircuit`` objects. It can be used by using the foo function,
    for example::

      from qiskit import foo
      from qiskit import QuantumCircuit
      foo(QuantumCircuit())

  - |
    The ``qiskit.QuantumCircuit`` module has a new method ``foo()``. This is
    the equivalent of calling the ``qiskit.foo()`` to do something to your
    QuantumCircuit. This is the equivalent of running ``qiskit.foo()`` on
    your circuit, but provides the convenience of running it natively on
    an object. For example::

      from qiskit import QuantumCircuit

      circ = QuantumCircuit()
      circ.foo()

deprecations:
  - |
    The ``qiskit.bar`` module has been deprecated and will be removed in a
    future release. Its sole function, ``foobar()`` has been superseded by the
    ``qiskit.foo()`` function which provides similar functionality but with
    more accurate results and better performance. You should update your calls
    ``qiskit.bar.foobar()`` calls to ``qiskit.foo()``.
```

You can also look at other release notes for other examples.

You can use any restructured text feature in them (code sections, tables,
enumerated lists, bulleted list, etc) to express what is being changed as
needed. In general you want the release notes to include as much detail as
needed so that users will understand what has changed, why it changed, and how
they'll have to update their code.

After you've finished writing your release notes you'll want to add the note
file to your commit with `git add` and commit them to your PR branch to make
sure they're included with the code in your PR.

##### Linking to issues

If you need to link to an issue or other github artifact as part of the release
note this should be done using an inline link with the text being the issue
number. For example you would write a release note with a link to issue 12345
as:

```yaml
fixes:
  - |
    Fixes a race condition in the function ``foo()``. Refer to
    `#12345 <https://github.com/Qiskit/qiskit-ibmq-provider/issues/12345>`_ for
    more details.
```

#### Generating the release notes

After release notes have been added if you want to see what the full output of
the release notes. In general the output from reno that we'll get is a rst
(ReStructuredText) file that can be compiled by
[sphinx](https://www.sphinx-doc.org/en/master/). To generate the rst file you
use the ``reno report`` command. If you want to generate the full ibmq provider
release notes for all releases (since we started using reno during 0.9) you just
run::

    reno report

but you can also use the ``--version`` argument to view a single release (after
it has been tagged::

    reno report --version 0.9.0

At release time ``reno report`` is used to generate the release notes for the
release and the output will be submitted as a pull request to the documentation
repository's [release notes file](
https://github.com/Qiskit/qiskit/blob/master/docs/release_notes.rst)

#### Building release notes locally

Building The release notes are part of the standard qiskit-ibmq-provider
documentation builds. To check what the rendered html output of the release
notes will look like for the current state of the repo you can run:
`tox -edocs` which will build all the documentation into `docs/_build/html`
and the release notes in particular will be located at
`docs/_build/html/release_notes.html`

## Installing Qiskit IBMQ Provider from source
Please see the [Installing IBM Quantum Provider from
Source](https://qiskit.org/documentation/contributing_to_qiskit.html#installing-ibm-quantum-provider-from-source)
section of the Qiskit documentation.


### Test

New features often imply changes in the existent tests or new ones are
needed. Once they\'re updated/added run this be sure they keep passing.

For executing the tests, a `make test` target is available.

For executing a simple python test manually, you can just run this
command:

Linux and Mac:

``` {.bash}
$ LOG_LEVEL=INFO python -m unittest test/test_something.py
```

Windows:

``` {.bash}
C:\..\> python -m unittest test/test_something.py
```

Note many of the tests will not be executed unless you have setup an
IBMQ account. To set this up please go to this
[page](https://quantum-computing.ibm.com/login) and
register an account.

By default, and if there is no user credentials available, the tests
that require online access are run with recorded (mocked) information.
This is, the remote requests are replayed from a `test/cassettes` and
not real HTTP requests is generated. If user credentials are found, in
that cases it use them to make the network requests.

How and which tests are executed is controlled by a environment variable
`QISKIT_TESTS`. The options are (where `uc_available = True` if the user
credentials are available, and `False` otherwise):

  ----------------------------------------------------------------------------------------------------
  Option          Description                             Default              If `True`, forces
  --------------- --------------------------------------- -------------------- -----------------------
  `skip_online`   Skips tests that require remote         `False`              `rec = False`
                  requests (also, no mocked information                        
                  is used). Does not require user                              
                  credentials.                                                 

  `mock_online`   It runs the online tests using mocked   `not uc_available`   `skip_online = False`
                  information. Does not require user                           
                  credentials.                                                 

  `run_slow`      It runs tests tagged as *slow*.         `False`              

  `rec`           It records the remote requests. It      `False`              `skip_online = False`
                  requires user credentials.                                   `run_slow = False`
  ----------------------------------------------------------------------------------------------------

It is possible to provide more than one option separated with commas.
The order of precedence in the options is right to left. For example,
`QISKIT_TESTS=skip_online,rec` will set the options as
`skip_online == False` and `rec == True`.

### Style guide

Please submit clean code and please make effort to follow existing
conventions in order to keep it as readable as possible. We use:
* [Pylint](https://www.pylint.org) linter
* [PEP 8](https://www.python.org/dev/peps/pep-0008) style
* [mypy](http://mypy-lang.org/) type hinting

To ensure your changes respect the style guidelines, you can run the following
commands:

All platforms:

``` {.sh}
$> cd out
out$> make lint
out$> make style
out$> make mypy
```

### Development Cycle

The development cycle for qiskit-ibmq-provider  is all handled in the open using
the project boards in Github for project management. We use milestones
in Github to track work for specific releases. The features or other changes
that we want to include in a release will be tagged and discussed in Github.
As we're preparing a new release we'll document what has changed since the
previous version in the release notes.

### Branches

* `master`:

The master branch is used for development of the next version of qiskit-ibmq-provider.
It will be updated frequently and should not be considered stable. The API
can and will change on master as we introduce and refine new features.

* `stable/*` branches:
Branches under `stable/*` are used to maintain released versions of qiskit-ibmq-provider.
It contains the version of the code corresponding to the latest release for
that minor version on pypi. For example, stable/0.8 contains the code for the
0.8.2 release on pypi. The API on these branches are stable and the only changes
merged to it are bugfixes.

### Release cycle

When it is time to release a new minor version of qiskit-ibmq-provider we will:

1.  Create a new tag with the version number and push it to github
2.  Change the `master` version to the next release version.

The release automation processes will be triggered by the new tag and perform
the following steps:

1.  Create a stable branch for the new minor version from the release tag
    on the `master` branch
2.  Build and upload binary wheels to pypi
3.  Create a github release page with a generated changelog
4.  Generate a PR on the meta-repository to bump the ibmq provider version and
    meta-package version.

The `stable/*` branches should only receive changes in the form of bug
fixes.
