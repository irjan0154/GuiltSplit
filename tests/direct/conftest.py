"""Shared fixtures for GuiltSplit Direct Mode tests."""

import os
import sys
from pathlib import Path

import pytest

# scripts/mutate.py points this at a mutated copy; the file name (stem) stays the same.
CONTRACT_PATH = os.environ.get("GUILTSPLIT_CONTRACT", "contracts/guilt_split.py")
MODULE_NAME = "_contract_" + Path(CONTRACT_PATH).stem


@pytest.fixture(scope="session")
def gs():
    """The loaded contract module: gives tests the pure functions and constants.

    genlayer-test imports the contract file as `_contract_<stem>`. The pure
    functions need no VM, so the module is loaded once per session and reused.
    """
    from gltest.direct.loader import create_address, deploy_contract
    from gltest.direct.vm import VMContext

    ctx = VMContext()
    ctx.sender = create_address("default_sender")
    with ctx.activate():
        deploy_contract(Path(CONTRACT_PATH).resolve(), ctx)
        # leaving activate() clears the module from sys.modules: keep our own reference
        module = sys.modules[MODULE_NAME]
    return module


@pytest.fixture
def world(direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie):
    """A fresh deployed contract; the default sender is alice."""
    from helpers import World

    contract = direct_deploy(CONTRACT_PATH)
    # use the module loaded for THIS test's VM: Address classes differ between loads
    module = sys.modules[MODULE_NAME]
    direct_vm.sender = direct_alice
    return World(direct_vm, contract, module, direct_alice, direct_bob, direct_charlie)


@pytest.fixture
def assessed(world):
    """Event registered, one case assessed (solo violation); mocks stay in place."""
    from helpers import answer

    world.register()
    world.serve()
    world.model(answer())
    world.cid = world.propose()
    world.outcome = world.assess(world.cid)
    return world
