from pathlib import Path

from oba import MODULE_CHANGES_FILE, apply_module_changes, jump_versions, load_module_changes

PRE_UPGRADE_FOLDER = Path(__file__).resolve().parent.parent


def migrate(cr, version):
    jump = "_".join(v.replace(".", "") for v in jump_versions(version))
    path = PRE_UPGRADE_FOLDER / jump / MODULE_CHANGES_FILE
    apply_module_changes(cr, version, *load_module_changes(path))
