from base_plugin import BasePlugin

def test_plugins_total():
    new_plugin = BasePlugin()
    assert new_plugin.plugins_total() == 1
