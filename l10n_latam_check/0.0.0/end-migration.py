from openupgradelib import openupgrade
from odoo import Command
import logging
_logger = logging.getLogger(__name__)


def adapt_journals(env):
    _logger.info('ajustando diarios de cheques de terceros')

    # recargamos la data para que se actualicen codes, nombres y demas
    openupgrade.load_data(env.cr, 'l10n_latam_check', 'data/account_payment_method_data.xml')

    # si diarios de cheques de terceros estaban como bank los pasamos a cash
    third_checks_journals = env['account.journal'].with_context(active_test=False).search([
        '|',
        ('inbound_payment_method_line_ids.payment_method_id', '=', env.ref('l10n_latam_check.account_payment_method_in_third_party_checks').id),
        ('outbound_payment_method_line_ids.payment_method_id', '=', env.ref('l10n_latam_check.account_payment_method_out_third_party_checks').id)])

    new_third_checks_id = env.ref('l10n_latam_check.account_payment_method_new_third_party_checks').id
    for tc_journal in third_checks_journals:
        if tc_journal.type != 'cash':
            tc_journal.write({'type': 'cash'})
        if new_third_checks_id not in tc_journal.inbound_payment_method_line_ids.mapped('payment_method_id').ids:
            tc_journal.write({
                'inbound_payment_method_line_ids': [
                    Command.create({
                        'payment_method_id': new_third_checks_id,
                        'sequence': 1,
                        })],
                })
    # por alguna razon el sequence anterior no anda, le pisamos con sequence 1
    env['account.payment.method.line'].search([('payment_method_id', '=', new_third_checks_id)]).write({'sequence': 1})

    _logger.info('creando diarios para cheques rechazados')
    # creamos diario de cheques propios
    # TODO como cuenta de este diario tenemos que usar la cuenta que estaba en la compañía de cheques rechazados
    env.cr.execute('select company_id from account_check_bu group by company_id;')
    company_ids = [x[0] for x in env.cr.fetchall()]
    for company_id in company_ids:
        env['account.journal'].create({
            'name': 'Cheques Rechazados',
            'type': 'cash',
            'code': 'CR99',
            'company_id': company_id,
            'outbound_payment_method_line_ids': [
                Command.create({'payment_method_id': env.ref(
                    'l10n_latam_check.account_payment_method_out_third_party_checks').id}),
            ],
            'inbound_payment_method_line_ids': [
                Command.create({'payment_method_id': env.ref(
                    'l10n_latam_check.account_payment_method_new_third_party_checks').id}),
                Command.create({'payment_method_id': env.ref(
                    'l10n_latam_check.account_payment_method_in_third_party_checks').id}),
            ]})


def adapt_own_checks(env):

    env.cr.execute("select id, state, name, payment_date from account_check_bu where type = 'issue_check'")
    checks_data = env.cr.fetchall()
    payment_model_id = env.ref('account.model_account_payment').id
    not_on_menu = []
    for check_id, check_state, check_number, check_payment_date in checks_data:
        if check_state == 'draft':
            _logger.info('Skipping check %s (id %s) as it is in draft', check_number, check_id)
            continue
        env.cr.execute(
            "select origin, operation, date from account_check_operation_bu where check_id = %s order by date asc, id asc",
            (check_id,))
        operations_data = env.cr.fetchall()

        # desde la primer operación buscamos el payment que va a reflejar el cheque. Ahora bien, si era una
        # importacion que se hizo mediante asientos, no va a quedar reflejado este cheque
        first_operation_origin = operations_data and operations_data[0][0] or False
        if first_operation_origin and 'account.payment' in first_operation_origin:
            check_payment_id = int(first_operation_origin.split(',')[1])
        else:
            check_payment_id = False

        check_payment = env['account.payment'].browse(check_payment_id)
        if not check_payment.exists():
            _logger.info('own check %s (id %s) was not created on a payment', check_number, check_id)
            not_on_menu.append((check_number, check_id))
            continue

        _logger.info('Migrating own check %s (id %s) on payment id %s', check_number, check_id, check_payment_id)
        check_payment = env['account.payment'].browse(check_payment_id)
        check_payment._write({
            'check_number': check_number,
            'l10n_latam_check_payment_date': check_payment_date,
        })
        # si esta debitado lo marcamos conciliado con banco por mas que no lo este
        if check_state == 'debited' and not check_payment.is_matched:
            check_payment._write({'is_matched': True})

        activities = env['mail.activity'].search([('res_id', '=', check_id), ('res_model', '=', 'account.check')])
        if activities:
            activities.write({'res_id': check_payment.id, 'res_model': 'account.payment', 'res_model_id': payment_model_id})
        attachments = env['ir.attachment'].search([('res_id', '=', check_id), ('res_model', '=', 'account.check')])
        if attachments:
            attachments.write({'res_id': check_payment.id, 'res_model': 'account.payment'})
        check_data = []
        for operation_origin, operation, operation_date in operations_data[1:]:
            operation_date = operation_date.strftime('%d/%m/%Y')
            if operation_origin:
                res_model, res_id = operation_origin.split(',')
                if res_model == 'account.check':
                    number = [x[0] == res_id and x[2] or ' ' for x in checks_data]
                    related_record_info = 'Cambio de cheque N°: %s' % number
                else:
                    related_record = env[res_model].browse(int(res_id))
                    related_record_info = related_record.display_name if related_record.exists() else \
                        'Registro no encontrado (%s, %s)' % (res_model, res_id)
                check_data.append("<li>%s: Operación de cheque '%s' con el registro <a href=# data-oe-model=%s data-oe-id=%d>%s</a></li>" % (
                    operation_date,
                    operation,
                    res_model, int(res_id),
                    related_record_info))
            else:
                check_data.append("<li>%s: Operación de cheque '%s' sin registro vinculado</li>" % (
                    operation_date,
                    operation,
                ))
        check_payment.message_post(body='Cheque migrado desde v13, información de operaciones:<br/><ul>%s</ul>' % ''.join(check_data))


def adapt_third_checks(env):
    new_third_checks_id = env.ref('l10n_latam_check.account_payment_method_new_third_party_checks').id
    payment_model_id = env.ref('account.model_account_payment').id
    checks_payment_method_lines_map = {
        x.journal_id.id: x for x in env['account.payment.method.line'].search([('payment_method_id', '=', new_third_checks_id)])}
    rejected_checks_journals_map = {
        x.company_id.id: x.id for x in env['account.journal'].search([('code', '=', 'CR99')])}

    third_on_hand_states = ['holding', 'rejected']

    env.cr.execute("select id, state, name, bank_id, owner_vat, payment_date, journal_id from account_check_bu where type = 'third_check'")
    checks_data = env.cr.fetchall()
    not_on_menu = []
    not_on_menu_on_hand = []
    # other_errors = []
    for check_id, check_state, check_number, check_bank_id, check_owner_vat, check_payment_date, current_journal_id in checks_data:
        if check_state == 'draft':
            _logger.info('Skipping check %s (id %s) as it is in draft', check_number, check_id)
            continue
        # TODO ordenarlas?
        env.cr.execute(
            "select origin, operation, date from account_check_operation_bu where check_id = %s order by date asc, id asc",
            (check_id,))
        operations_data = env.cr.fetchall()

        # desde la primer operación buscamos el payment que va a reflejar el cheque. Ahora bien, si era una
        # importacion que se hizo mediante asientos, no va a quedar reflejado este cheque
        first_operation_origin = operations_data and operations_data[0][0] or False
        if first_operation_origin and 'account.payment' in first_operation_origin:
            check_payment_id = int(first_operation_origin.split(',')[1])
        else:
            check_payment_id = False
        check_payment = env['account.payment'].browse(check_payment_id)
        if not check_payment.exists():
            if check_state in third_on_hand_states:
                _logger.warning('third check %s (id %s) was not created on a payment and is on hand!', check_number, check_id)
                not_on_menu_on_hand.append((check_number, check_id))
            else:
                _logger.info('third check %s (id %s) was not created on a payment and is not on hand', check_number, check_id)
                not_on_menu.append((check_number, check_id))
            continue

        if check_state == 'holding':
            # usamos current_journal_id en vez de payment.journal_id porque podria haber sido transferido
            journal_id = current_journal_id
        elif check_state == 'rejected':
            journal_id = rejected_checks_journals_map.get(check_payment.company_id.id)
        else:
            journal_id = None
        activities = env['mail.activity'].search([('res_id', '=', check_id), ('res_model', '=', 'account.check')])
        if activities:
            activities.write({'res_id': check_payment.id, 'res_model': 'account.payment', 'res_model_id': payment_model_id})
        attachments = env['ir.attachment'].search([('res_id', '=', check_id), ('res_model', '=', 'account.check')])
        if attachments:
            attachments.write({'res_id': check_payment.id, 'res_model': 'account.payment'})
        _logger.info('Migrating third check %s (id %s) on payment id %s', check_number, check_id, check_payment_id)
        check_payment._write({
            'payment_method_line_id': checks_payment_method_lines_map[check_payment.journal_id.id].id,
            'payment_method_id': checks_payment_method_lines_map[check_payment.journal_id.id].payment_method_id.id,
            'check_number': check_number,
            'l10n_latam_check_bank_id': check_bank_id,
            'l10n_latam_check_issuer_vat': check_owner_vat,
            'l10n_latam_check_payment_date': check_payment_date,
            'l10n_latam_check_current_journal_id': journal_id,
        })

        check_data = []
        for operation_origin, operation, operation_date in operations_data[1:]:
            operation_date = operation_date.strftime('%d/%m/%Y')

            if operation_origin:
                res_model, res_id = operation_origin.split(',')
                related_record = env[res_model].browse(int(res_id))
                related_record_info = related_record.display_name if related_record.exists() else \
                    'Registro no encontrado (%s, %s)' % (res_model, res_id)
                check_data.append("<li>%s: Operación de cheque '%s' con el registro <a href=# data-oe-model=%s data-oe-id=%d>%s</a></li>" % (
                    operation_date,
                    operation,
                    res_model, int(res_id),
                    related_record_info))
            else:
                check_data.append("<li>%s: Operación de cheque '%s' sin registro vinculado</li>" % (
                    operation_date,
                    operation,
                ))
        check_payment.message_post(body='Cheque migrado desde v13, información de operaciones:<br/><ul>%s</ul>' % ''.join(check_data))

        # error.append('Cheque %s, esta en cartera pero no fue originado con un payment')
        # info.append('Cheque %s fue originado con un asiento manual, en la nueva version no figura en listado de cheques pero ya no estaba mas en cartera)


@openupgrade.migrate()
def migrate(env, version):
    adapt_journals(env)
    adapt_third_checks(env)
    adapt_own_checks(env)
