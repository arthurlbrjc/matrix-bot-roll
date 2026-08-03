"""
Parses `CHANGELOG.md` (Keep a Changelog format) and answers `!changes`:
"what's changed since the last release of a given granularity".

`CHANGELOG.md` lives at the repo root, alongside `src/` — resolved relative
to this file rather than the process's cwd, so it's found the same way
whether run via `invoke run` (cwd = repo root) or in the Docker image
(`COPY . .` into `/app`, `WORKDIR /app`, module run as `-m matrix_bot_roll.main`).
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Literal, Optional, Tuple, Union

from matrix_bot_roll.messages import INVALID_GRANULARITY, NO_RELEASES

CHANGELOG_PATH = Path(__file__).resolve().parent.parent.parent / "CHANGELOG.md"

Granularity = Literal["major", "minor", "patch"]
_GRANULARITIES: Tuple[Granularity, ...] = ("major", "minor", "patch")

_RELEASE_HEADING_RE = re.compile(
    r"^## \[(\d+)\.(\d+)\.(\d+)\](?: - (.+))?\s*$", re.MULTILINE
)


@dataclass
class Release:
    """
    One `## [X.Y.Z]` section of `CHANGELOG.md`: its version, and its body
    exactly as written (headings, bullets, everything after the version
    heading up to the next one).
    """

    version: Tuple[int, int, int]
    date: Optional[str]
    body: str

    def __str__(self) -> str:
        header = f"[{'.'.join(map(str, self.version))}]"
        if self.date:
            header += f" - {self.date}"
        return f"## {header}\n{self.body}".rstrip()


@dataclass
class ChangesCommand:
    """A fully parsed `!changes [major|minor|patch]` request, ready for the caller to answer with the matching releases."""

    granularity: Granularity


def build_changes_command(body: str) -> Union[ChangesCommand, str]:
    """Parse a full `!changes` message body: bare (implies `minor`), or `!changes major|minor|patch`."""
    parts = body.split(maxsplit=1)
    if len(parts) < 2:
        return ChangesCommand(granularity="minor")

    arg = parts[1].strip().lower()
    if arg not in _GRANULARITIES:
        return INVALID_GRANULARITY
    return ChangesCommand(granularity=arg)  # type: ignore[arg-type]


def parse_changelog(path: Path = CHANGELOG_PATH) -> List[Release]:
    """Parse every `## [X.Y.Z] - date` section out of the changelog at `path`, most recent first (matching file order)."""
    text = path.read_text()
    headings = list(_RELEASE_HEADING_RE.finditer(text))

    releases = []
    for index, heading in enumerate(headings):
        major, minor, patch, date = heading.groups()
        start = heading.end()
        end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        body = text[start:end].strip("\n")
        releases.append(
            Release(version=(int(major), int(minor), int(patch)), date=date, body=body)
        )
    return releases


def select_releases(releases: List[Release], granularity: Granularity) -> List[Release]:
    """
    Select every release since the last one of `granularity`, inclusive of
    that boundary release, from `releases` (most recent first).

    "The last release of granularity G" is the most recent candidate not
    equal to the latest release itself:

    - `major` candidates are `X.0.0` releases, `minor` candidates are `X.Y.0`
      releases, `patch` candidates are every release.
    - If the latest release is itself a candidate (e.g. latest is `X.Y.0`
      and granularity is `minor`), it can't be its own boundary, so the
      boundary falls back to the previous candidate instead — which is what
      makes the default (`minor`) show the *whole* last minor cycle when
      currently sitting on a fresh `.0` release, per the issue's resolved
      default: "since the last minor release, or since the previous minor
      if currently on a .0".
    - For `patch`, every release is a candidate, so the latest is always
      self-excluded and the boundary is simply the previous release —
      degrading to "just the last two releases", which is the sensible
      floor for the finest granularity.

    No special-casing is needed between the three: the same rule produces
    all three behaviors depending only on which releases count as
    candidates.
    """
    if not releases:
        return []

    latest = releases[0]
    candidates = [
        release for release in releases if _matches_granularity(release, granularity)
    ]
    # `releases` is sorted most-recent-first, so is `candidates`; the latest
    # release can't be its own boundary, so drop it if it's the first candidate.
    if candidates and candidates[0].version == latest.version:
        candidates = candidates[1:]

    if not candidates:
        return releases  # no earlier release of this granularity — show everything

    boundary_version = candidates[0].version
    boundary_index = next(
        index
        for index, release in enumerate(releases)
        if release.version == boundary_version
    )
    return releases[: boundary_index + 1]


def _matches_granularity(release: Release, granularity: Granularity) -> bool:
    """Whether `release` counts as a release of `granularity` (an `X.0.0`, `X.Y.0`, or any release, respectively)."""
    _, minor, patch = release.version
    if granularity == "major":
        return minor == 0 and patch == 0
    if granularity == "minor":
        return patch == 0
    return True


def format_changes(releases: List[Release]) -> str:
    """Render the selected releases (most recent first) as the `!changes` reply body, or `NO_RELEASES` if there are none."""
    if not releases:
        return NO_RELEASES
    return "\n\n".join(str(release) for release in releases)
