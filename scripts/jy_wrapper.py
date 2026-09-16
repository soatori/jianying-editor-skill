"""Compatibility imports for existing-project operations.

The former wrapper mixed generation and existing-draft mutation. Existing
projects now use one canonical runtime.
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
