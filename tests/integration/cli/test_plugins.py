from ape_plugins.utils import FIRST_CLASS_PLUGINS, SECOND_CLASS_PLUGINS

INSTALLED_CORE_PLUGINS_HEADER = "Installed Core Plugins"
INSTALLED_PLUGINS_HEADER = "Installed Plugins"
AVAILABLE_PLUGINS_HEADER = "Available Plugins"


# test plugins list with github access token and no 2nd class or third class installed
def test_plugins_list_nothing_installed(ape_cli, runner):
    result = runner.invoke(ape_cli, ["plugins", "list"])
    assert result.exit_code == 0, result.output  # no errors when it runs
    assert "No plugins installed\n" == result.output


def assert_plugins_in_output(plugins, output, header):
    expected_plugins = [p.replace("ape_", "") for p in plugins if p != "ape"]
    for plugin in expected_plugins:
        assert_in_section(plugin, output, header)


def assert_in_section(plugin, output, expected_section):

    headers = [INSTALLED_CORE_PLUGINS_HEADER, INSTALLED_PLUGINS_HEADER, AVAILABLE_PLUGINS_HEADER]
    headers = [h for h in headers if h in output]  # filter headers

    output = output.strip().split("\n\n")
    output = [item.split("\n  ") for item in output]
    output = {item[0].strip(":"): item[1:] for item in output}
    output[INSTALLED_PLUGINS_HEADER] = [
        tuple(item.split("     ")) for item in output[INSTALLED_PLUGINS_HEADER]
    ]

    actual_core_plugins = set(output[INSTALLED_CORE_PLUGINS_HEADER])
    actual_install_plugins = set(output[INSTALLED_PLUGINS_HEADER])
    actual_available_plugins = set(output[AVAILABLE_PLUGINS_HEADER])

    # we show each set of the plugins are unique from other sets of plugins
    assert actual_core_plugins.isdisjoint(actual_install_plugins)
    assert actual_install_plugins.isdisjoint(actual_available_plugins)
    assert actual_available_plugins.isdisjoint(actual_core_plugins)

    expected_core_plugins = {p.replace("ape_", "") for p in FIRST_CLASS_PLUGINS if p != "ape"}
    expected_second_plugins = {p.replace("ape_", "") for p in SECOND_CLASS_PLUGINS if p != "ape"}

    # Core is all First Class Plugins
    assert expected_core_plugins == actual_core_plugins
    # Second Class are ether in installed or available
    breakpoint()
    assert expected_second_plugins == {name for name, _ in actual_install_plugins}.union(
        actual_available_plugins
    )


# test plugins list -a with github access token and no 2nd class or third class installed
def test_plugins_list_all(ape_cli, runner):
    result = runner.invoke(ape_cli, ["plugins", "list", "-a"])
    assert result.exit_code == 0  # no errors when it runs

    assert_plugins_in_output(FIRST_CLASS_PLUGINS, result.output, INSTALLED_CORE_PLUGINS_HEADER)
    assert_plugins_in_output(SECOND_CLASS_PLUGINS, result.output, AVAILABLE_PLUGINS_HEADER)
    assert_plugins_in_output(SECOND_CLASS_PLUGINS, result.output, INSTALLED_PLUGINS_HEADER)

    # all list available accessible only if you have github token
    # display everything as a plugins and as installed
    # with github token display availble
    # make a mock 3rd class plugins and live in the test directory
    # for testing purpose


def test_install_uninstall_plugins(ape_cli, runner):

    # ape plugins add vyper -y
    result = runner.invoke(ape_cli, ["plugins", "add", "vyper", "-y"])
    # result = runner.invoke(ape_cli, "plugins", "add", "jules", "-y")

    # breakpoint()
    assert result.exit_code == 0  # no errors when it runs
    assert "INFO: Installing ape_vyper...\n" in result.output

    """
(apeworx) chris@DESKTOP-ID4V0R6:~/ape$ ape plugins list
Installed Plugins:
  vyper     0.1.0a7
  jules      0.1.dev10+g0ca16f6)


    """

    # ape plugins list
    result = runner.invoke(ape_cli, ["plugins", "list"])
    assert result.exit_code == 0  # no errors when it runs
    assert "Installed Plugins:" in result.output

    # ape plugins list -a
    result = runner.invoke(ape_cli, ["plugins", "list", "-a"])
    assert result.exit_code == 0  # no errors when it runs
    assert "Installed Core Plugins:" in result.output
    assert "Installed Plugins:" in result.output
    assert "Available Plugins:" in result.output
    # second class
    # third class name

    # ape plugins remove vyper -y
    result = runner.invoke(ape_cli, ["plugins", "remove", "vyper", "-y"])

    # NOTHING NO RESPONSE

    result = runner.invoke(ape_cli, ["plugins", "list"])
    assert result.exit_code == 0  # no errors when it runs
    assert "No plugins installed" in result.output


def setup_plugins():
    # Set github token to test token
    #
    # user_token = environ['GITHUB_ACCESS_TOKEN']
    # environ['GITHUB_ACCESS_TOKEN'] = 'TEST'
    # plugins run a script to install plugins
    pass


def unintall_plugins():
    # runs script to uninstall plugins
    pass


def test_github_access_token(ape_cli, runner, monkeypatch):
    # from ape_plugins import utils
    # monkeypatch.setattr(utils, "SECOND_CLASS_PLUGINS", set())

    result = runner.invoke(ape_cli, ["plugins", "list"])
    breakpoint()
    assert result.exit_code == 0, "Exit was not successful"
    assert "$GITHUB_ACCESS_TOKEN not set, skipping 2nd class plugins\n" in result.output

    # github token invoke with enviorment in click documenation test cli apps
    # isolate installed enviorment during testing
