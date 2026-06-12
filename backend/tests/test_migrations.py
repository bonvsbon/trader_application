from __future__ import annotations

from alembic.config import Config
from alembic.script import ScriptDirectory


def test_revision_ids_fit_default_alembic_version_column():
    script = ScriptDirectory.from_config(Config("alembic.ini"))

    for revision in script.walk_revisions():
        assert len(revision.revision) <= 32, revision.revision

