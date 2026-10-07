"""Don't break on selection fields of models that are gone.

In ``modules/base/0.0.0`` so it runs on every jump from 20 on; until 19 each version folder
has its own copy.
"""

from odoo.addons.base.models.ir_model import IrModelFieldsSelection

from oba import should_run

_original_method = IrModelFieldsSelection._process_ondelete


def _process_ondelete(self):
    """Don't break on missing models when deleting their selection fields"""
    to_process = self.browse([])
    for selection in self:
        try:
            self.env[selection.field_id.model]  # pylint: disable=pointless-statement
            to_process += selection
        except KeyError:
            continue
    return _original_method(to_process)


def migrate(cr, version):
    if not should_run(cr, version):
        return
    IrModelFieldsSelection._process_ondelete = _process_ondelete
