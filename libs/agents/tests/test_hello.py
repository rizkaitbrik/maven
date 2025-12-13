"""Hello unit test module."""

from agents.hello import hello


def test_hello():
    """Test the hello function."""
    assert hello() == "Hello agents"
