# Offline integration consumer

This is an adaptation of the accepted HEB-154 requirements-readiness specialist.
It retains its 91 synthetic control cases and SDK mock-wire checks. It is test-only
and is not distributed with Bedrock. There is no live CLI in this fixture.

Install the bundled core and requirements-lock.txt into a disposable Python 3.11+
virtual environment, then run `python run_offline_tests.py --evidence-dir NEW_DIRECTORY`.
Use `--hygiene-file` for the operator-provided private exclusion file; otherwise a
populated synthetic list exercises the same sanitization path without private data.
The runner removes API credentials; SDK tests use an in-memory HTTP transport.

Adaptations: installed-wheel bootstrap and hash verification, explicit temporary
evidence root and hygiene input, portable interpreter selection, core-compatible
rpds-py/typing-extensions pins. Core and adapter mechanisms remain the accepted
source except these integration bindings. The historical build trace, first
failures, live results and original source identities are retained separately in
HEB-154 repository integration evidence and the immutable accepted-trial archive.
These offline checks do not rerun or extend the accepted eight-case live trial.
