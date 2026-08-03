import os

# Sanity limits on dice count/sides/expressions-per-command to prevent abuse;
# overridable via env for deployments that want stricter or looser bounds.
MAX_DICE_COUNT = int(os.environ.get("MAX_DICE_COUNT", 100))
MAX_DICE_SIDES = int(os.environ.get("MAX_DICE_SIDES", 100))
MAX_DICE_EXPRESSIONS = int(os.environ.get("MAX_DICE_EXPRESSIONS", 3))

# Every saved pattern for every user lives in one shared account-data blob
# (see saved_patterns.py), which Synapse caps at ~65KB — this bounds how much
# of that budget one user can claim, so one heavy user can't lock the rest out.
MAX_SAVED_PATTERNS_PER_USER = int(os.environ.get("MAX_SAVED_PATTERNS_PER_USER", 25))
MAX_PATTERN_NAME_LENGTH = int(os.environ.get("MAX_PATTERN_NAME_LENGTH", 32))

# Caps the per-room "last roll"/"last detail" memory (see lru_dict.py) so a bot
# invited into unboundedly many rooms over a long uptime doesn't leak memory.
MAX_TRACKED_ROOMS = int(os.environ.get("MAX_TRACKED_ROOMS", 1000))

VERBOSE_FLAGS = {"-v", "--verbose"}
