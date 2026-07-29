import os

# Sanity limits on dice count/sides to prevent abuse; overridable via env for
# deployments that want stricter or looser bounds.
MAX_DICE_COUNT = int(os.environ.get("MAX_DICE_COUNT", 100))
MAX_DICE_SIDES = int(os.environ.get("MAX_DICE_SIDES", 100))
