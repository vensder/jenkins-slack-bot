from base_plugin import BasePlugin

def test_plugins_total():
    new_plugin = BasePlugin(Plugin)
    assert new_plugin.plugins_total == 3
