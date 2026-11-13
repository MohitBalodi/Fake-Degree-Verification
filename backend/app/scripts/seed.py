"""Seed demo users and institutions (synthetic data only).

Run: docker compose exec api python -m app.scripts.seed
"""

import sys


def main() -> int:
    print("seed: nothing to seed yet - models land with Tier 1 (auth + registry).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
