import pytest

from ape_plugins.utils import FIRST_CLASS_PLUGINS, SECOND_CLASS_PLUGINS

from .utils import skip_projects_except

INSTALLED_CORE_PLUGINS_HEADER = "Installed Core Plugins"
INSTALLED_PLUGINS_HEADER = "Installed Plugins"
AVAILABLE_PLUGINS_HEADER = "Available Plugins"


# test plugins list with github access token and no 2nd class or third class installed
def test_plugins_list_nothing_installed(ape_cli, runner):
    result = runner.invoke(ape_cli, ["plugins", "list"])
    assert result.exit_code == 0, result.output  # no errors when it runs
    assert "No plugins installed\n" == result.output


def parse_section_into_sets(output):

    # headers = [INSTALLED_CORE_PLUGINS_HEADER, INSTALLED_PLUGINS_HEADER, AVAILABLE_PLUGINS_HEADER]
    # headers = [h for h in headers if h in output]  # filter headers
    output = output.strip().split("\n\n")
    output = [item.split("\n  ") for item in output]
    output = {item[0].strip(":"): item[1:] for item in output}
    if INSTALLED_PLUGINS_HEADER in output:
        output[INSTALLED_PLUGINS_HEADER] = [
            tuple(item.split("     ")) for item in output[INSTALLED_PLUGINS_HEADER]
        ]
        actual_install_plugins = set(output[INSTALLED_PLUGINS_HEADER])

    actual_core_plugins = set(output[INSTALLED_CORE_PLUGINS_HEADER])
    actual_available_plugins = set(output[AVAILABLE_PLUGINS_HEADER])

    if INSTALLED_PLUGINS_HEADER in output:
        return actual_core_plugins, actual_install_plugins, actual_available_plugins
    else:
        return actual_core_plugins, actual_available_plugins


def assert_sections(output):

    if len(parse_section_into_sets(output)) > 2:
        (
            actual_core_plugins,
            actual_install_plugins,
            actual_available_plugins,
        ) = parse_section_into_sets(output)
    else:
        actual_core_plugins, actual_available_plugins = parse_section_into_sets(output)
        actual_install_plugins = set()
    # we show each set of the plugins are unique from other sets of plugins
    assert actual_core_plugins.isdisjoint(actual_install_plugins)
    assert actual_install_plugins.isdisjoint(actual_available_plugins)
    assert actual_available_plugins.isdisjoint(actual_core_plugins)

    expected_core_plugins = {p.replace("ape_", "") for p in FIRST_CLASS_PLUGINS if p != "ape"}
    expected_second_plugins = {p.replace("ape_", "") for p in SECOND_CLASS_PLUGINS if p != "ape"}

    # Core is all First Class Plugins
    assert expected_core_plugins == actual_core_plugins
    # Second Class are ether in installed or available
    assert expected_second_plugins == {name for name, _ in actual_install_plugins}.union(
        actual_available_plugins
    )


# test plugins list -a with github access token and no 2nd class or third class installed
def test_plugins_list_all(ape_cli, runner):
    result = runner.invoke(ape_cli, ["plugins", "list", "-a"])
    assert result.exit_code == 0  # no errors when it runs

    assert_sections(result.output)
    assert_sections(result.output)
    assert_sections(result.output)

    # TODO make a mock 3rd class plugins and live in the test directory


@pytest.mark.xfail(reason="Not sure why ape plugins list is not verifiying install properly")
# TODO make a skip_all_projects
@skip_projects_except(["unregistered-contracts"])
def test_install(ape_cli, runner):

    """
    1. list plugins (make sure it is not installed) by looking for "Installed Pugins" header
    2. Add solidity
    3. Assert that there are no errors when installing
    4. Check to make sure vyper or solidity is in the Installed Plugins
    5. Remove the plugins
    6. Check to see if "Installed Plugins:" header is there
    """

    result = runner.invoke(ape_cli, ["plugins", "list", "-a"])
    assert "Installed Plugins:\n" not in result.output

    result = runner.invoke(ape_cli, ["plugins", "add", "solidity", "-y"])
    assert result.exit_code == 0, result.output  # no errors when it runs
    assert "Installing ape_solidity...\n" in result.output

    result = runner.invoke(ape_cli, ["plugins", "list", "-a"])
    assert result.exit_code == 0

    # TODO It is should find the solidity plugin and show assert that it is in the output
    assert "Installed Plugins:\n" in result.output
    assert "solidity" in result.output

    result = runner.invoke(ape_cli, ["plugins", "remove", "solidity", "-y"])
    assert result.exit_code == 0

    result = runner.invoke(ape_cli, ["plugins", "list", "-a"])
    assert "Installed Plugins:\n" not in result.output


def test_github_access_token(ape_cli, runner, monkeypatch):
    # from ape_plugins import utils
    # monkeypatch.setattr(utils, "SECOND_CLASS_PLUGINS", set())

    result = runner.isolation(ape_cli, ["plugins", "list"], env={"GITHUB_ACCESS_TOKEN": "TEST"})
    breakpoint()
    assert result.exit_code == 0, "Exit was not successful"
    assert "$GITHUB_ACCESS_TOKEN not set, skipping 2nd class plugins\n" in result.output

    # github token invoke with enviorment in click documenation test cli apps
    # isolate installed enviorment during testing
