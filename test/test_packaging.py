import unittest
from pathlib import Path

try:
    import tomllib
except ImportError:  # pragma: no cover - python < 3.11
    import tomli as tomllib


class TestPackagingDependencies(unittest.TestCase):
    """This plugin emits stream URIs prefixed with ``rss//`` and ``news//``.
    Those prefixes are only playable if the stream-extractor plugins that
    register them are installed, so they must be hard dependencies, not
    optional extras."""

    def setUp(self):
        pyproject = Path(__file__).parent.parent / "pyproject.toml"
        with open(pyproject, "rb") as f:
            self.data = tomllib.load(f)
        self.dependencies = self.data["project"]["dependencies"]

    def _find_dep(self, name):
        return [d for d in self.dependencies if d.split(">")[0].split("=")[0].split("<")[0].strip() == name]

    def test_rss_extractor_is_a_hard_dependency(self):
        matches = self._find_dep("ovos-ocp-rss-plugin")
        self.assertTrue(matches, "ovos-ocp-rss-plugin (owns the rss// prefix) must be a hard dependency")
        self.assertIn(">=", matches[0], "ovos-ocp-rss-plugin must be floor-pinned")

    def test_news_extractor_is_a_hard_dependency(self):
        matches = self._find_dep("ovos-ocp-news-plugin")
        self.assertTrue(matches, "ovos-ocp-news-plugin (owns the news// prefix) must be a hard dependency")
        self.assertIn(">=", matches[0], "ovos-ocp-news-plugin must be floor-pinned")


if __name__ == "__main__":
    unittest.main()
