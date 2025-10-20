from odoo.addons.base.models.ir_model import (
    IrModelFieldsSelection as IrModelSelection,
)


_original_method = IrModelSelection._process_ondelete


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


IrModelSelection._process_ondelete = _process_ondelete


def migrate(cr, version):
    pass
