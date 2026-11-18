from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic" / "alembic.ini"


def _script() -> ScriptDirectory:
    return ScriptDirectory.from_config(Config(str(ALEMBIC_INI)))


def test_migration_history_has_at_most_one_head():
    # Two branches that add a migration on the same parent give two heads after the merge.
    # A new project without a migration has no head.
    heads = _script().get_heads()
    assert len(heads) <= 1, (
        f"Alembic has {len(heads)} heads: {heads}. On a work branch, set down_revision to the "
        "current head after the rebase. Do not add a merge migration there."
    )


def test_merge_revisions_list_no_ancestor_as_a_parent():
    script = _script()
    for revision in script.walk_revisions():
        parents = revision.down_revision
        if not isinstance(parents, tuple):
            continue
        for parent in parents:
            ancestors = {ancestor.revision for ancestor in script.iterate_revisions(parent, "base")}
            assert not (set(parents) - {parent}) & ancestors, f"{revision.revision} lists an ancestor as a parent"
