"""Tests against real Home Assistant on Linux; all device I/O is mocked."""

import pytest


@pytest.fixture(autouse=True)
def enable_integration(enable_custom_integrations):
    yield


@pytest.fixture
def config_data():
    return {
        "name": "Living room AVR", "host": "192.0.2.15", "port": 10025,
        "wake_device": "harman_kardon", "wake_command": "power_on", "wake_timeout": 5,
    }
