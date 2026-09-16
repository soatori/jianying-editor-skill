"""Compatibility entry point for the canonical Jianying project runtime.

DEPRECATED: prefer `python scripts/jianying_project.py <command> ...`.
Retained so old docs/commands keep working.
"""

from jianying_project import main


if __name__ == "__main__":
    raise SystemExit(main())
