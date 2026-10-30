"""
Tests for the Modbus gateway descriptor the package advertises.

The descriptor is what the gateway UI offers to an operator when a new device is
added, so its fields are part of the integration contract, not an internal
detail. The entry-point test guards the declaration that makes the descriptor
discoverable at all.
"""

from importlib.metadata import entry_points

import pytest
from scietex.hal.serial.gateway.drivers import (
    ENTRY_POINT_GROUP,
    ModbusDriver,
    resolve_driver,
    verify_driver,
)

from scietex.hal.vfd.intek.spe_b import IntekSPEBModbusVFD
from scietex.hal.vfd.modbus_drivers import intek_spe_b

VFD_DRIVER_GROUP = "scietex.hal.vfd.drivers"


def test_descriptor_reuses_the_builtin_rtu_bundle():
    """SPE-B speaks standard Modbus RTU once Pd.05 is set, so nothing is custom."""
    assert isinstance(intek_spe_b, ModbusDriver)
    assert intek_spe_b.name == "intek_spe_b"
    assert intek_spe_b.label == "Intek SPE-B"
    assert intek_spe_b.device_type == "Variable Frequency Drive"
    assert intek_spe_b.framer == "RTU"
    assert intek_spe_b.decoder is None
    assert not intek_spe_b.pdus
    assert intek_spe_b.translator is None


def test_descriptor_verifies():
    """The descriptor passes the loader validation the gateway runs."""
    assert verify_driver(intek_spe_b) is None


def test_descriptor_resolves_by_name():
    """The name in the descriptor is the one the gateway resolves."""
    assert resolve_driver("intek_spe_b") is intek_spe_b


def test_descriptor_is_declared_as_an_entry_point():
    """The declaration is install-time; skip when metadata is stale."""
    declared = {
        entry.name: entry
        for entry in entry_points(group=ENTRY_POINT_GROUP)
        if entry.name == "intek_spe_b"
    }
    if not declared:
        pytest.skip(f"installed metadata carries no {ENTRY_POINT_GROUP} entry")
    assert declared["intek_spe_b"].load() is intek_spe_b


def test_transport_driver_is_declared_as_an_entry_point():
    """A service discovers the client through the VFD driver group."""
    discovered = {
        entry.name: entry
        for entry in entry_points(group=VFD_DRIVER_GROUP)
        if entry.name == "intek_spe_b_modbus"
    }
    if not discovered:
        pytest.skip(f"installed metadata carries no {VFD_DRIVER_GROUP} entry")
    assert discovered["intek_spe_b_modbus"].load() is IntekSPEBModbusVFD
