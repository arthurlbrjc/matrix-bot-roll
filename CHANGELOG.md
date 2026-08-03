# Changelog

All notable changes to this project are documented here, in the format
described by [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

Entries below `v1.5.0` are documented retroactively from the commit history —
not rewritten to look prettier than they were, just organized by section.

## [1.5.0] - 2026-08-03

### Added

- `!save`/`!s` command to save a named roll pattern, and `!roll <name>` to reuse it
- `!save --list` to list a user's saved patterns
- `!forget`/`!f` command to remove a saved pattern

### Changed

- Capped the number of room watched to prevent overusage of memory
- Added a limit on how many dice expressions can be rolled in a single command

## [1.4.1] - 2026-07-31

### Fixed

- Clarified an error message

## [1.4.0] - 2026-07-31

### Added

- Attach or override a target on `!reroll`
- Attach or override a message on `!reroll`

### Fixed

- Shortened `!reroll` output to terse by default
- Only remember a roll for `!reroll` after it validates successfully
- Removed a stale mention of `!detail` from `!roll --help`

## [1.3.0] - 2026-07-30

### Changed

- Roll results are terse by default; added `-v`/`--verbose` and `!detail` to show the full per-die breakdown

## [1.2.1] - 2026-07-30

### Added

- A roll auto-succeeds/fails its target on a crit or fumble

## [1.2.0] - 2026-07-29

### Added

- Target-number comparisons (e.g. `>15`) on a roll, for pass/fail

## [1.1.2] - 2026-07-29

### Added

- Command aliases (`!r`, `!rr`, `!d`)

## [1.1.1] - 2026-07-28

### Changed

- Deploy now polls for status before proceeding, to wait out transient states

## [1.1.0] - 2026-07-25

Internal reorganization only — no user-facing changes.

## [1.0.0] - 2026-07-25

First stable release.

## [0.4.3] - 2026-07-25

### Added

- `!roll --help`

## [0.4.2] - 2026-07-24

### Changed

- Widened log suppression and made it configurable

## [0.4.1] - 2026-07-24

### Fixed

- Skip backlog messages on connect; quieted noisy `nio` crypto logging

## [0.4.0] - 2026-07-24

### Added

- Support for starting a fresh Matrix session on every deploy, for non-persistent storage

## [0.3.0] - 2026-07-24

### Added

- Attach a message to a roll (`| message`)

## [0.2.0] - 2026-07-24

### Added

- Dice count/sides limits configurable via env vars

### Fixed

- Allow the extra advantage/disadvantage die to exceed the dice count limit
- Prevent a crash when a room key was already requested

### Changed

- Deploy directly via the Scaleway API, no CLI install in CI

## [0.1.0] - 2026-07-23

Initial release.

### Added

- `!roll`/`!reroll` dice rolling for Matrix
- Keep highest/lowest dice (`kh`/`kl`)
- Per-die modifiers applied before summing
- Crit/fumble tracking
- Opt-in health-check HTTP endpoint
- JSON logging
- Docker image and Compose setup
