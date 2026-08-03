"""Unit tests for CHANGELOG.md parsing and `!changes` granularity selection in changelog.py."""

from matrix_bot_roll.changelog import (
    ChangesCommand,
    build_changes_command,
    format_changes,
    parse_changelog,
    select_releases,
)
from matrix_bot_roll.messages import INVALID_GRANULARITY, NO_RELEASES

_SAMPLE_CHANGELOG = """\
# Changelog

## [1.4.1] - 2026-07-31
### Fixed
- clarify error message

## [1.4.0] - 2026-07-31
### Added
- reroll overrides

## [1.3.0] - 2026-07-30
### Changed
- terse by default

## [1.0.0]
First stable release.

## [0.1.0] - 2026-07-23
### Added
- initial release
"""


def _write_changelog(tmp_path, text=_SAMPLE_CHANGELOG):
    path = tmp_path / "CHANGELOG.md"
    path.write_text(text)
    return path


class TestParseChangelog:
    def test_parses_every_release_most_recent_first(self, tmp_path):
        releases = parse_changelog(_write_changelog(tmp_path))
        assert [release.version for release in releases] == [
            (1, 4, 1),
            (1, 4, 0),
            (1, 3, 0),
            (1, 0, 0),
            (0, 1, 0),
        ]

    def test_parses_date(self, tmp_path):
        releases = parse_changelog(_write_changelog(tmp_path))
        assert releases[0].date == "2026-07-31"

    def test_body_excludes_the_heading_and_stops_before_the_next_release(
        self, tmp_path
    ):
        releases = parse_changelog(_write_changelog(tmp_path))
        body = releases[0].body  # 1.4.1
        assert "clarify error message" in body
        assert "reroll overrides" not in body
        assert "## [" not in body

    def test_release_without_a_date_parses(self, tmp_path):
        releases = parse_changelog(_write_changelog(tmp_path))
        first_stable = next(r for r in releases if r.version == (1, 0, 0))
        assert first_stable.date is None
        assert "First stable release." in first_stable.body


class TestSelectReleases:
    def _versions(self, releases):
        return [release.version for release in releases]

    def test_minor_default_since_last_minor_when_on_a_patch_release(self, tmp_path):
        releases = parse_changelog(_write_changelog(tmp_path))  # latest: 1.4.1
        selected = select_releases(releases, "minor")
        assert self._versions(selected) == [(1, 4, 1), (1, 4, 0)]

    def test_minor_falls_back_to_previous_minor_when_currently_on_a_dot_zero(
        self, tmp_path
    ):
        # Latest release (1.5.0) is itself a minor boundary, so per the
        # issue's resolved default it can't be its own boundary — falls back
        # to the previous minor (1.4.0), spanning the whole 1.4.x cycle.
        text = _SAMPLE_CHANGELOG.replace(
            "## [1.4.1]", "## [1.5.0]\n### Added\n- x\n\n## [1.4.1]", 1
        )
        releases = parse_changelog(_write_changelog(tmp_path, text))
        selected = select_releases(releases, "minor")
        assert self._versions(selected) == [(1, 5, 0), (1, 4, 1), (1, 4, 0)]

    def test_patch_shows_only_the_last_two_releases(self, tmp_path):
        releases = parse_changelog(_write_changelog(tmp_path))  # latest: 1.4.1
        selected = select_releases(releases, "patch")
        assert self._versions(selected) == [(1, 4, 1), (1, 4, 0)]

    def test_major_shows_everything_since_the_last_major(self, tmp_path):
        releases = parse_changelog(_write_changelog(tmp_path))  # latest: 1.4.1
        selected = select_releases(releases, "major")
        assert self._versions(selected) == [
            (1, 4, 1),
            (1, 4, 0),
            (1, 3, 0),
            (1, 0, 0),
        ]

    def test_no_earlier_release_of_the_granularity_shows_everything(self, tmp_path):
        text = "\n".join(
            line
            for line in _SAMPLE_CHANGELOG.splitlines()
            if "[1.0.0]" not in line and "[0.1.0]" not in line
        )
        text += "\n## [1.0.0] - 2026-07-25\nFirst stable release.\n"
        releases = parse_changelog(_write_changelog(tmp_path, text))
        selected = select_releases(releases, "major")
        assert self._versions(selected) == self._versions(releases)

    def test_empty_changelog_selects_nothing(self):
        assert select_releases([], "minor") == []


class TestBuildChangesCommand:
    def test_bare_defaults_to_minor(self):
        result = build_changes_command("!changes")
        assert result == ChangesCommand(granularity="minor")

    def test_explicit_granularity(self):
        assert build_changes_command("!changes major") == ChangesCommand(
            granularity="major"
        )
        assert build_changes_command("!changes minor") == ChangesCommand(
            granularity="minor"
        )
        assert build_changes_command("!changes patch") == ChangesCommand(
            granularity="patch"
        )

    def test_granularity_is_case_insensitive(self):
        assert build_changes_command("!changes MAJOR") == ChangesCommand(
            granularity="major"
        )

    def test_invalid_granularity_returns_error(self):
        assert build_changes_command("!changes bogus") == INVALID_GRANULARITY


class TestFormatChanges:
    def test_no_releases_returns_no_releases_message(self):
        assert format_changes([]) == NO_RELEASES

    def test_renders_selected_releases(self, tmp_path):
        releases = parse_changelog(_write_changelog(tmp_path))
        selected = select_releases(releases, "patch")
        text = format_changes(selected)
        assert "[1.4.1] - 2026-07-31" in text
        assert "clarify error message" in text
        assert "[1.4.0] - 2026-07-31" in text
        assert "reroll overrides" in text
