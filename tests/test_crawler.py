import pytest
from bots.advancer import AdvancerBot

def test_advancer_init():
    bot = AdvancerBot()
    assert bot.som_js_path.exists()
    script = bot._read_som_script()
    assert "applySetOfMark" in script
