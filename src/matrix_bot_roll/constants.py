import os

# Sanity limits on dice count/sides to prevent abuse; overridable via env for
# deployments that want stricter or looser bounds.
MAX_DICE_COUNT = int(os.environ.get("MAX_DICE_COUNT", 100))
MAX_DICE_SIDES = int(os.environ.get("MAX_DICE_SIDES", 100))

# Every saved pattern for every user lives in one shared account-data blob
# (see saved_patterns.py), which Synapse caps at ~65KB — this bounds how much
# of that budget one user can claim, so one heavy user can't lock the rest out.
MAX_SAVED_PATTERNS_PER_USER = int(os.environ.get("MAX_SAVED_PATTERNS_PER_USER", 25))
MAX_PATTERN_NAME_LENGTH = int(os.environ.get("MAX_PATTERN_NAME_LENGTH", 32))

VERBOSE_FLAGS = {"-v", "--verbose"}
