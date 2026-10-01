from oba import apply_module_changes

MERGE_MODULES = []
RENAMED_MODULES = []
RENAMED_XMLIDS = []


def migrate(cr, version):
    apply_module_changes(cr, version, MERGE_MODULES, RENAMED_MODULES, RENAMED_XMLIDS)
