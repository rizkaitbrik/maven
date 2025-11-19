"""Hello unit test module."""

from cli.hello import hello


def test_hello():
    """Test the hello function."""
    assert hello() == "Hello cli"
