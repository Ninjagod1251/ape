import copy
import shutil

import click
import pytest

from ape.cli import (
    AccountAliasPromptChoice,
    ConnectedProviderCommand,
    NetworkBoundCommand,
    NetworkChoice,
    PromptChoice,
    account_option,
    config_override_option,
    contract_file_paths_argument,
    existing_alias_argument,
    network_option,
    non_existing_alias_argument,
    select_account,
    verbosity_option,
)
from ape.cli.choices import _NONE_NETWORK, _get_networks_sequence_from_cache
from ape.cli.commands import get_param_from_ctx, parse_network
from ape.exceptions import AccountsError
from ape.logging import logger
from tests.conftest import geth_process_test, skip_if_plugin_installed

OUTPUT_FORMAT = "__TEST__{0}:{1}:{2}_"
OTHER_OPTION_VALUE = "TEST_OTHER_OPTION"
other_option = click.option("--other", default=OTHER_OPTION_VALUE)


@pytest.fixture
def keyfile_swap_paths(config):
    return config.DATA_FOLDER / "accounts", config.DATA_FOLDER.parent / "temp_accounts"


@pytest.fixture
def one_keyfile_account(keyfile_swap_paths, keyfile_account, temp_config):
    src_path, dest_path = keyfile_swap_paths
    existing_keyfiles = [x for x in src_path.iterdir() if x.is_file()]
    test_data = {"test": {"number_of_accounts": 0}}
    if existing_keyfiles == [keyfile_account.keyfile_path]:
        # Already only has the 1 account
        with temp_config(test_data):
            yield keyfile_account

    else:
        if dest_path.is_file():
            dest_path.unlink()
        elif dest_path.is_dir():
            shutil.rmtree(dest_path)

        dest_path.mkdir()
        for keyfile in [x for x in existing_keyfiles if x != keyfile_account.keyfile_path]:
            shutil.copy(keyfile, dest_path / keyfile.name)
            keyfile.unlink()

        with temp_config(test_data):
            yield keyfile_account

        for file in dest_path.iterdir():
            shutil.copy(file, src_path / file.name)


@pytest.fixture
def network_cmd():
    @click.command()
    @network_option()
    def cmd(ecosystem, network, provider):
        output = OUTPUT_FORMAT.format(ecosystem.name, network.name, provider.name)
        click.echo(output)

    return cmd


@pytest.fixture
def contracts_paths_cmd():
    expected = "EXPECTED {}"

    @click.command()
    @contract_file_paths_argument()
    def cmd(file_paths):
        output = ", ".join(x.name for x in sorted(file_paths))
        click.echo(expected.format(output))

    return cmd


def _setup_temp_acct_number_change(accounts, num_accounts: int):
    if "containers" in accounts.__dict__:
        del accounts.__dict__["containers"]

    installed_account_types = {str(type(a)) for a in accounts}
    if installed_account_types:
        accounts_str = ", ".join(installed_account_types)
        pytest.fail(f"Unable to side-step install of account type(s): {accounts_str}")

    return {"test": {"number_of_accounts": num_accounts}}


def _teardown_numb_acct_change(accounts):
    if "containers" in accounts.__dict__:
        del accounts.__dict__["containers"]


@pytest.fixture
def no_accounts(accounts, empty_data_folder, temp_config):
    data = _setup_temp_acct_number_change(accounts, 0)
    with temp_config(data):
        yield

    _teardown_numb_acct_change(accounts)


@pytest.fixture
def one_account(accounts, empty_data_folder, temp_config, test_accounts):
    data = _setup_temp_acct_number_change(accounts, 1)
    with temp_config(data):
        yield test_accounts[0]

    _teardown_numb_acct_change(accounts)


def get_expected_account_str(acct):
    return f"__expected_output__: {acct.address}"


def test_select_account_no_accounts_found(no_accounts):
    with pytest.raises(AccountsError, match="No accounts found."):
        assert not select_account()


def test_select_account_one_account(runner, one_account):
    # No input needed when only one account
    account = select_account()
    assert account == one_account


def test_select_account_multiple_accounts_requires_input(
    runner, keyfile_account, second_keyfile_account
):
    with runner.isolation(input="0\n"):
        account = select_account()

    assert account == keyfile_account


def test_select_account_custom_prompt(runner, keyfile_account, second_keyfile_account):
    prompt = "THIS_IS_A_CUSTOM_PROMPT"
    with runner.isolation(input="0\n") as out_streams:
        select_account(prompt)
        output = out_streams[0].getvalue().decode()

    assert prompt in output


def test_select_account_specify_type(runner, one_keyfile_account):
    with runner.isolation():
        account = select_account(key=type(one_keyfile_account))

    assert account == one_keyfile_account


def test_select_account_unknown_type(runner, keyfile_account):
    with pytest.raises(AccountsError) as err:
        select_account(key=str)  # type: ignore

    assert "Cannot return accounts with type '<class 'str'>'" in str(err.value)


def test_select_account_with_account_list(runner, keyfile_account, second_keyfile_account):
    account = select_account(key=[keyfile_account])
    assert account == keyfile_account

    account = select_account(key=[second_keyfile_account])
    assert account == second_keyfile_account

    with runner.isolation(input="1\n"):
        account = select_account(key=[keyfile_account, second_keyfile_account])
        assert account == second_keyfile_account


def test_network_option_default(runner, network_cmd):
    result = runner.invoke(network_cmd, catch_exceptions=False)
    assert result.exit_code == 0, result.output
    assert OUTPUT_FORMAT.format("ethereum", "local", "test") in result.output


def test_network_option_specified(runner, network_cmd):
    network_part = ("--network", "ethereum:local:test")
    result = runner.invoke(network_cmd, network_part)
    assert result.exit_code == 0, result.output
    assert OUTPUT_FORMAT.format("ethereum", "local", "test") in result.output


def test_network_option_unknown(runner, network_cmd):
    network_part = ("--network", "UNKNOWN")
    result = runner.invoke(network_cmd, network_part)
    assert result.exit_code != 0


def test_network_option_with_other_option(runner):
    """
    To prove can use the `@network_option` with other options
    in the same command (was issue during production where could not!).
    """

    # Scenario: Using network_option but not using the value in the command callback.
    #  (Potentially handling independently).
    @click.command()
    @network_option()
    @other_option
    def solo_option(other):
        click.echo(other)

    # Scenario: Using the network option with another option.
    # This use-case is way more common than the one above.
    @click.command()
    @network_option()
    @other_option
    def with_net(network, other):
        click.echo(network.name)
        click.echo(other)

    def run(cmd, fail_msg=None):
        res = runner.invoke(cmd, (), catch_exceptions=False)
        fail_msg = f"{fail_msg}\n{res.output}" if fail_msg else res.output
        assert res.exit_code == 0, fail_msg
        assert OTHER_OPTION_VALUE in res.output, fail_msg
        return res

    run(solo_option, fail_msg="Failed when used without network kwargs")
    result = run(with_net, fail_msg="Failed when used with network kwargs")
    assert "local" in result.output


@pytest.mark.parametrize(
    "network_input",
    (
        "ethereum:custom:https://127.0.0.1:4545",
        "ethereum:custom:https://127.0.0.1",
        "ethereum:custom:http://127.0.0.1:4545",
        "ethereum:custom:http://127.0.0.1",
        "ethereum:custom:http://foo.bar",
        "ethereum:custom:https://foo.bar:8000",
        ":custom:https://foo.bar:8000",
        "::https://foo.bar:8000",
        "https://foo.bar:8000",
    ),
)
def test_network_option_custom_uri(runner, network_cmd, network_input):
    network_part = ("--network", network_input)
    result = runner.invoke(network_cmd, network_part)
    assert result.exit_code == 0, result.output
    assert "custom" in result.output


def test_network_option_existing_network_with_custom_uri(runner, network_cmd):
    network_part = ("--network", "ethereum:sepolia:https://foo.bar:8000")
    result = runner.invoke(network_cmd, network_part)
    assert result.exit_code == 0, result.output
    assert "sepolia" in result.output


def test_network_option_make_required(runner):
    @click.command()
    @network_option(required=True)
    def cmd(network):
        click.echo(OUTPUT_FORMAT.format(network))

    result = runner.invoke(cmd, ())
    assert result.exit_code == 2
    assert "Error: Missing option '--network'." in result.output


def test_network_option_default_none(runner):
    @click.command()
    @network_option(default=None)
    def cmd(network):
        click.echo(f"Value is '{network}'")

    result = runner.invoke(cmd)
    assert "Value is 'None'" in result.output


def test_network_option_specified_none(runner):
    @click.command()
    @network_option()
    def cmd(network):
        click.echo(f"Value is '{network}'")

    result = runner.invoke(cmd, ("--network", "None"))
    assert "Value is 'None'" in result.output


@pytest.mark.parametrize("network_name", ("apenet", "apenet1"))
def test_network_option_specify_custom_network(runner, custom_networks_config, network_name):
    network_part = ("--network", f"ethereum:{network_name}:geth")

    # NOTE: Also testing network filter with a custom network
    #  But this is also required to work around LRU cache
    #  giving us the wrong networks because click is running
    #  the tester in-process after re-configuring networks,
    #  which shouldn't happen IRL.

    @click.command()
    @network_option(network=network_name)
    def cmd(network):
        click.echo(f"Value is '{network.name}'")

    result = runner.invoke(cmd, network_part)
    assert f"Value is '{network_name}'" in result.output


def test_account_option(runner, keyfile_account):
    @click.command()
    @account_option()
    def cmd(account):
        _expected = get_expected_account_str(account)
        click.echo(_expected)

    expected = get_expected_account_str(keyfile_account)
    result = runner.invoke(cmd, ("--account", keyfile_account.alias))
    assert expected in result.output


def test_account_option_uses_single_account_as_default(runner, one_account):
    """
    When there is only 1 test account, that is the default
    when no option is given.
    """

    @click.command()
    @account_option(account_type=[one_account])
    def cmd(account):
        _expected = get_expected_account_str(account)
        click.echo(_expected)

    expected = get_expected_account_str(one_account)
    result = runner.invoke(cmd, ())
    assert expected in result.output


def test_account_prompts_when_more_than_one_keyfile_account(
    runner, keyfile_account, second_keyfile_account
):
    @click.command()
    @account_option()
    def cmd(account):
        _expected = get_expected_account_str(account)
        click.echo(_expected)

    expected = get_expected_account_str(keyfile_account)

    # Requires user input.
    result = runner.invoke(cmd, (), input="0\n")

    assert expected in result.output


def test_account_option_can_use_test_account(runner, test_accounts):
    index = 7
    test_account = test_accounts[index]

    @click.command()
    @account_option()
    def cmd(account):
        _expected = get_expected_account_str(account)
        click.echo(_expected)

    expected = get_expected_account_str(test_account)
    result = runner.invoke(cmd, ("--account", f"TEST::{index}"))
    assert expected in result.output


@pytest.mark.parametrize("opt", (0, "foo"))
def test_prompt_choice(runner, opt):
    """
    This demonstrates how to use ``PromptChoice``,
    as it is a little confusing, requiring a callback.
    """

    def choice_callback(ctx, param, value):
        return param.type.select()

    choice = PromptChoice(["foo", "bar"])
    assert hasattr(choice, "name")
    choice = PromptChoice(["foo", "bar"], name="choice")
    assert choice.name == "choice"

    @click.command()
    @click.option(
        "--choice",
        type=choice,
        callback=choice_callback,
    )
    def cmd(choice):
        click.echo(f"__expected_{choice}")

    result = runner.invoke(cmd, [], input=f"{opt}\n")
    assert "Select one of the following:" in result.output
    assert "__expected_foo" in result.output


def test_verbosity_option(runner):
    @click.command()
    @verbosity_option()
    def cmd():
        click.echo(f"__expected_{logger.level}")

    result = runner.invoke(cmd, ["--verbosity", logger.level])
    assert f"__expected_{logger.level}" in result.output


def test_account_prompt_name():
    """
    It is very important for this class to have the `name` attribute,
    even though it is not used. That is because some click internals
    expect this property to exist, and we skip the super() constructor.
    """
    option = AccountAliasPromptChoice()
    assert option.name == "account"
    option = AccountAliasPromptChoice(name="account_z")
    assert option.name == "account_z"


def test_contract_file_paths_argument_given_source_id(
    project_with_source_files_contract, runner, contracts_paths_cmd
):
    pm = project_with_source_files_contract
    src_id = next(iter(pm.sources))
    result = runner.invoke(contracts_paths_cmd, src_id)
    assert f"EXPECTED {src_id}" in result.output


def test_contract_file_paths_argument_given_name(
    project_with_source_files_contract, runner, contracts_paths_cmd
):
    pm = project_with_source_files_contract
    src_stem = next(iter(pm.sources)).split(".")[0]
    result = runner.invoke(contracts_paths_cmd, src_stem)
    assert f"EXPECTED {src_stem}" in result.output


def test_contract_file_paths_argument_given_contracts_folder(
    project_with_contract, runner, contracts_paths_cmd
):
    pm = project_with_contract
    result = runner.invoke(contracts_paths_cmd, pm.contracts_folder.as_posix())
    all_paths = ", ".join(x.name for x in sorted(pm.source_paths))
    assert f"EXPECTED {all_paths}" in result.output


def test_contract_file_paths_argument_given_contracts_folder_name(
    project_with_contract, runner, contracts_paths_cmd
):
    pm = project_with_contract
    result = runner.invoke(contracts_paths_cmd, "contracts")
    all_paths = ", ".join(x.name for x in sorted(pm.source_paths))
    assert f"EXPECTED {all_paths}" in result.output


@pytest.mark.parametrize("name", ("contracts/subdir", "subdir"))
def test_contract_file_paths_argument_given_subdir_relative_to_path(
    project_with_contract, runner, contracts_paths_cmd, name
):
    pm = project_with_contract
    result = runner.invoke(contracts_paths_cmd, name)
    all_paths = ", ".join(x.name for x in sorted(pm.source_paths) if x.parent.name == "subdir")
    assert f"EXPECTED {all_paths}" in result.output


@skip_if_plugin_installed("vyper")
def test_contract_file_paths_argument_missing_vyper(
    project_with_source_files_contract, runner, contracts_paths_cmd
):
    name = "VyperContract"
    result = runner.invoke(contracts_paths_cmd, name)
    expected = (
        "Missing compilers for the following file types: '.vy'. "
        "Possibly, a compiler plugin is not installed or is installed "
        "but not loading correctly. Is 'ape-vyper' installed?"
    )
    assert expected in result.output


@skip_if_plugin_installed("solidity")
def test_contract_file_paths_argument_missing_solidity(
    project_with_source_files_contract, runner, contracts_paths_cmd
):
    name = "SolidityContract"
    result = runner.invoke(contracts_paths_cmd, name)
    expected = (
        "Missing compilers for the following file types: '.sol'. "
        "Possibly, a compiler plugin is not installed or is installed "
        "but not loading correctly. Is 'ape-solidity' installed?"
    )
    assert expected in result.output


def test_existing_alias_option(runner):
    @click.command()
    @existing_alias_argument()
    def cmd(alias):
        click.echo(alias)

    result = runner.invoke(cmd, "TEST::0")
    assert "TEST::0" in result.output


def test_existing_alias_option_custom_callback(runner):
    magic_value = "THIS IS A TEST"

    def custom_callback(*args, **kwargs):
        return magic_value

    @click.command()
    @existing_alias_argument(callback=custom_callback)
    def cmd(alias):
        click.echo(alias)

    result = runner.invoke(cmd, "TEST::0")
    assert magic_value in result.output


def test_non_existing_alias_option(runner):
    @click.command()
    @non_existing_alias_argument()
    def cmd(alias):
        click.echo(alias)

    result = runner.invoke(cmd, "non-exists")
    assert "non-exists" in result.output


def test_non_existing_alias_option_custom_callback(runner):
    magic_value = "THIS IS A TEST"

    def custom_callback(*args, **kwargs):
        return magic_value

    @click.command()
    @non_existing_alias_argument(callback=custom_callback)
    def cmd(alias):
        click.echo(alias)

    result = runner.invoke(cmd, "non-exists")
    assert magic_value in result.output


def test_connected_provider_command_no_args_or_network_specified(runner):
    @click.command(cls=ConnectedProviderCommand)
    def cmd():
        from ape import chain

        click.echo(chain.provider.is_connected)

    result = runner.invoke(cmd)
    assert result.exit_code == 0
    assert "True" in result.output, result.output


def test_connected_provider_command_invalid_value(runner):
    @click.command(cls=ConnectedProviderCommand)
    def cmd():
        pass

    result = runner.invoke(cmd, ("--network", "OOGA_BOOGA"), catch_exceptions=False)
    assert result.exit_code != 0
    assert "Invalid value for '--network'" in result.output


def test_connected_provider_command_use_provider(runner):
    @click.command(cls=ConnectedProviderCommand)
    def cmd(provider):
        click.echo(provider.is_connected)

    result = runner.invoke(cmd)
    assert result.exit_code == 0
    assert "True" in result.output, result.output


def test_connected_provider_command_use_ecosystem_network_and_provider(runner):
    @click.command(cls=ConnectedProviderCommand)
    def cmd(ecosystem, network, provider):
        click.echo(f"{ecosystem.name}:{network.name}:{provider.name}")

    result = runner.invoke(cmd)
    assert result.exit_code == 0
    assert "ethereum:local:test" in result.output, result.output


def test_connected_provider_command_use_ecosystem_network_and_provider_with_network_specified(
    runner,
):
    @click.command(cls=ConnectedProviderCommand)
    def cmd(ecosystem, network, provider):
        click.echo(f"{ecosystem.name}:{network.name}:{provider.name}")

    result = runner.invoke(cmd, ["--network", "ethereum:local:test"])
    assert result.exit_code == 0
    assert "ethereum:local:test" in result.output, result.output


def test_connected_provider_command_use_custom_options(runner):
    """
    Ensure custom options work when using `ConnectedProviderCommand`.
    (There was an issue during development where we could not).
    """

    # Scenario: Custom option and using network object.
    @click.command(cls=ConnectedProviderCommand)
    @other_option
    def use_net(network, other):
        click.echo(network.name)
        click.echo(other)

    # Scenario: Only using custom option.
    @click.command(cls=ConnectedProviderCommand)
    @other_option
    def solo_other(other):
        click.echo(other)

    @click.command(cls=ConnectedProviderCommand)
    @click.argument("other_arg")
    @other_option
    def with_arg(other_arg, other, provider):
        click.echo(other)
        click.echo(provider.name)
        click.echo(other_arg)

    spec = ("--network", "ethereum:local:test")

    def run(cmd, extra_args=None):
        arguments = [*spec, *(extra_args or [])]
        res = runner.invoke(cmd, arguments, catch_exceptions=False)
        assert res.exit_code == 0, res.output
        assert OTHER_OPTION_VALUE in res.output
        return res

    result = run(use_net)
    assert "local" in result.output, result.output  # Echos network object

    result = run(solo_other)
    assert "local" not in result.output, result.output

    argument = "_extra_"
    result = run(with_arg, extra_args=[argument])
    assert "test" in result.output
    assert argument in result.output


@geth_process_test
def test_connected_provider_command_with_network_option(runner, geth_provider):
    _ = geth_provider  # Ensure already running, to avoid clashing later on.

    @click.command(cls=ConnectedProviderCommand)
    @network_option()
    def cmd(provider):
        click.echo(provider.name)

    # NOTE: Must use a network that is not the default.
    spec = ("--network", "ethereum:local:geth")
    res = runner.invoke(cmd, spec, catch_exceptions=False)
    assert res.exit_code == 0, res.output
    assert "geth" in res.output


def test_connected_provider_command_none_network(runner):
    @click.command(cls=ConnectedProviderCommand)
    def cmd(network, provider):
        click.echo(network)
        click.echo(provider)

    spec = ("--network", "None")
    res = runner.invoke(cmd, spec, catch_exceptions=False)
    assert res.exit_code == 0, res.output


# TODO: Delete for 0.8.
def test_deprecated_network_bound_command(runner):
    with pytest.warns(
        DeprecationWarning,
        match=r"'NetworkBoundCommand' is deprecated\. Use 'ConnectedProviderCommand'\.",
    ):

        @click.command(cls=NetworkBoundCommand)
        @network_option()
        # NOTE: Must also make sure can use other options with this combo!
        #   (was issue where could not).
        @click.option("--other", default=OTHER_OPTION_VALUE)
        def cmd(network, other):
            click.echo(network)
            click.echo(other)

    result = runner.invoke(cmd, ["--network", "ethereum:local:test"], catch_exceptions=False)
    assert result.exit_code == 0, result.output
    assert "ethereum:local:test" in result.output, result.output
    assert OTHER_OPTION_VALUE in result.output


def test_get_param_from_ctx(mocker):
    mock_ctx = mocker.MagicMock()
    mock_ctx.params = {"foo": "bar"}
    mock_ctx.parent = mocker.MagicMock()
    mock_ctx.parent.params = {"interactive": True}
    actual = get_param_from_ctx(mock_ctx, "interactive")
    assert actual is True


def test_parse_network_when_interactive_and_no_param(mocker):
    ctx = mocker.MagicMock()
    ctx.params = {"interactive": True}
    ctx.parent = None
    network_ctx = parse_network(ctx)
    assert network_ctx is not None
    assert network_ctx.provider.name == "test"
    assert network_ctx._disconnect_on_exit is False  # Because of interactive: True


def test_parse_network_when_interactive_and_str_param(mocker):
    ctx = mocker.MagicMock()
    ctx.params = {"interactive": True, "network": "ethereum:local:test"}
    network_ctx = parse_network(ctx)
    assert network_ctx is not None
    assert network_ctx.provider.name == "test"
    assert network_ctx._disconnect_on_exit is False  # Because of interactive: True


def test_parse_network_when_interactive_and_class_param(mocker, eth_tester_provider):
    ctx = mocker.MagicMock()
    ctx.params = {"interactive": True, "network": eth_tester_provider}
    network_ctx = parse_network(ctx)
    assert network_ctx is not None
    assert network_ctx.provider.name == "test"
    assert network_ctx._disconnect_on_exit is False  # Because of interactive: True


def test_parse_network_when_explicit_none(mocker):
    ctx = mocker.MagicMock()
    ctx.params = {"network": _NONE_NETWORK}
    network_ctx = parse_network(ctx)
    assert network_ctx is None


def test_network_choice():
    network_choice = NetworkChoice()
    actual = network_choice.convert("ethereum:local:test", None, None)
    assert actual.name == "test"
    assert actual.network.name == "local"


@pytest.mark.parametrize("prefix", ("", "ethereum:custom:"))
def test_network_choice_custom_adhoc_network(prefix):
    network_choice = NetworkChoice()
    uri = "https://example.com"
    actual = network_choice.convert(f"{prefix}{uri}", None, None)
    assert actual.uri == uri
    assert actual.network.name == "custom"


def test_network_choice_custom_config_network(custom_networks_config_dict, temp_config):
    data = copy.deepcopy(custom_networks_config_dict)

    # Was a bug where couldn't have this name.
    data["networks"]["custom"][0]["name"] = "custom"

    _get_networks_sequence_from_cache.cache_clear()

    network_choice = NetworkChoice()
    with temp_config(data):
        actual = network_choice.convert("ethereum:custom", None, None)

    assert actual.network.name == "custom"


def test_network_choice_when_custom_local_network():
    network_choice = NetworkChoice()
    uri = "https://example.com"
    actual = network_choice.convert(f"ethereum:local:{uri}", None, None)
    assert actual.uri == uri
    assert actual.network.name == "local"


def test_network_choice_explicit_none():
    network_choice = NetworkChoice()
    actual = network_choice.convert("None", None, None)
    assert actual == _NONE_NETWORK


def test_config_override_option(runner):
    @click.command()
    @config_override_option()
    def cli(config_override):
        assert isinstance(config_override, dict)
        assert config_override["foo"] == "bar"

    result = runner.invoke(cli, ("--config-override", '{"foo": "bar"}'))
    assert result.exit_code == 0
    assert not result.exception
