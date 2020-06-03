#!/usr/bin/env python3
"""
"""
import pytest

from caper.cromwell import Cromwell


def pytest_addoption(parser):
    parser.addoption(
        '--ci-prefix', default='default_ci_prefix', help='Prefix for CI test.'
    )
    parser.addoption(
        '--s3-root',
        default='s3://encode-test-autouri/tmp',
        help='S3 root path for CI test. '
        'This S3 bucket must be configured without versioning. '
        'Make it publicly accessible. '
        'Read access for everyone is enough for testing. ',
    )
    parser.addoption(
        '--gcs-root',
        default='gs://encode-test-autouri/tmp',
        help='GCS root path for CI test. '
        'This GCS bucket must be publicly accessible '
        '(read access for everyone is enough for testing).',
    )
    parser.addoption(
        '--cromwell',
        default=Cromwell.DEFAULT_CROMWELL,
        help='URI for Cromwell JAR. Local path is recommended.',
    )
    parser.addoption(
        '--womtool',
        default=Cromwell.DEFAULT_WOMTOOL,
        help='URI for Womtool JAR. Local path is recommended.',
    )


@pytest.fixture(scope="session")
def ci_prefix(request):
    return request.config.getoption("--ci-prefix").rstrip('/')


@pytest.fixture(scope="session")
def s3_root(request):
    """S3 root to generate test S3 URIs on.
    """
    return request.config.getoption("--s3-root").rstrip('/')


@pytest.fixture(scope="session")
def gcs_root(request):
    """GCS root to generate test GCS URIs on.
    """
    return request.config.getoption("--gcs-root").rstrip('/')


@pytest.fixture(scope="session")
def cromwell(request):
    return request.config.getoption("--cromwell")


@pytest.fixture(scope="session")
def womtool(request):
    return request.config.getoption("--wooltool")
