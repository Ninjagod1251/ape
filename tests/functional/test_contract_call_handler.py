import pytest

from ape.contracts.base import ContractCallHandler
from ape.exceptions import ContractNotFoundError


def test_struct_input(
    call_handler_with_struct_input, struct_input_for_call, output_from_struct_input_call
):
    actual = call_handler_with_struct_input.encode_input(*struct_input_for_call)
    assert actual == output_from_struct_input_call


def test_call_contract_not_found(mocker, method_abi_with_struct_input):
    contract = mocker.MagicMock()
    contract.is_contract = False
    method = method_abi_with_struct_input
    handler = ContractCallHandler(contract=contract, abis=[method])
    expected = ".*Current network 'ethereum:local:test'.*"
    with pytest.raises(ContractNotFoundError, match=expected):
        handler()


def test_transact_contract_not_found(mocker, owner, method_abi_with_struct_input):
    contract = mocker.MagicMock()
    contract.is_contract = False
    method = method_abi_with_struct_input
    handler = ContractCallHandler(contract=contract, abis=[method])
    expected = ".*Current network 'ethereum:local:test'.*"
    with pytest.raises(ContractNotFoundError, match=expected):
        handler.transact(sender=owner)
