"""Compatibility imports for existing-project operations.

DEPRECATED: prefer `from jianying_project import ...` directly.
Retained for inbound imports; not an alternate write path.
"""

from jianying_project import (
    JianyingProject,
    ProjectError,
    assemble_keep_blocks,
    validate_content,
    validate_keep_blocks,
)

__all__ = [
    "JianyingProject",
    "ProjectError",
    "assemble_keep_blocks",
    "validate_content",
    "validate_keep_blocks",
]
