from openupgradelib import openupgrade
from odoo import Command, fields
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
        journal = env['account.journal'].create({
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
        journal.outbound_payment_method_line_ids.write({'payment_account_id': journal.default_account_id.id})
        journal.inbound_payment_method_line_ids.write({'payment_account_id': journal.default_account_id.id})


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
    third_checks_journals = env['account.payment.method.line'].search([('payment_method_id', '=', new_third_checks_id)]).mapped('journal_id')
    # checks_payment_manual_method_lines_map = {}
    manual_payment_method = env.ref('account.account_payment_method_manual_in')
    manual_payment_method_line = env['account.payment.method.line'].search([('payment_method_id', '=', manual_payment_method.id), ('journal_id', '=', False)], limit=1)
    if not manual_payment_method_line:
        manual_payment_method_line = env['account.payment.method.line'].create({
            'payment_method_id': manual_payment_method.id,
            'name': 'Manual',
        })
    # for journal in third_checks_journals:
    #     manual_method = journal.inbound_payment_method_line_ids.filtered(
    #         lambda pm: pm.payment_method_id == env.ref('l10n_latam_check.account_payment_method_in_third_party_checks')):
    #     if not manual_method:
    #         manual_method = journal.create
    #     checks_payment_method_lines_map[journal.id] = manual_method
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
        check_data = []
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
        # si el no está en mano (journal_id = False) y la fecha de pago (o del payment si no tiene fecha de pago) es 
        # anterior a 60 dias, entonces NO lo creamos como un cheque para no tener que crearle transaccion acomodando
        # diario actual
        # si llega a ser necesario podemos hacer parametrizable el dato de 60 como un conf parameter
        check_date = check_payment.l10n_latam_check_payment_date or check_payment.date
        if not journal_id and (fields.Date.today() - check_date).days > 60:
            payment_method_line_id = manual_payment_method_line.id
            payment_method_id = manual_payment_method.id
            payment_as_check = False
        else:
            payment_method_line_id = checks_payment_method_lines_map[check_payment.journal_id.id].id
            payment_method_id = checks_payment_method_lines_map[check_payment.journal_id.id].payment_method_id.id
            payment_as_check = True
        check_payment._write({
            'payment_method_line_id': payment_method_line_id,
            'payment_method_id': payment_method_id,
            'check_number': check_number,
            'l10n_latam_check_bank_id': check_bank_id,
            'l10n_latam_check_issuer_vat': check_owner_vat,
            'l10n_latam_check_payment_date': check_payment_date,
            'l10n_latam_check_current_journal_id': journal_id,
        })
        # check payment journa es el diario donde se cobro / genera el cheque
        # journal es el diario de v13 donde esta el cheque
        if payment_as_check and check_payment.journal_id.id != journal_id:
            if journal_id:
                payment_type = 'inbound'
                new_pay_journal_id = journal_id
                payment_method_line = env["account.journal"].browse(new_pay_journal_id).inbound_payment_method_line_ids.filtered(
                    lambda pm: pm.payment_method_id == env.ref('l10n_latam_check.account_payment_method_in_third_party_checks'))
            else:
                payment_type = 'outbound'
                new_pay_journal_id = check_payment.journal_id.id
                payment_method_line = check_payment.journal_id.outbound_payment_method_line_ids.filtered(
                    lambda pm: pm.payment_method_id == env.ref('l10n_latam_check.account_payment_method_out_third_party_checks'))
            payment_transaction = env['account.payment'].create({
                'l10n_latam_check_id': check_payment.id,
                'date': check_payment.date,
                'payment_type': payment_type,
                'payment_method_line_id': payment_method_line.id,
                'journal_id': new_pay_journal_id,
                'partner_id': check_payment.partner_id.id,
                'amount': 0.0,
                'ref': 'Migration payment for updating current journal of check %s' % check_payment.name,
            })
            # llamamos a post del move que es lo que hace el action_post para hacer bypass a las constraints de latam
            # check en action_post
            payment_transaction.move_id._post(soft=False)
            print ('payment_transaction', payment_transaction)
            # payment_transaction.action_post()
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
        if payment_as_check and check_data:
            check_payment.message_post(body='Cheque migrado desde v13, información de operaciones:<br/><ul>%s</ul>' % ''.join(check_data))
        elif not payment_as_check:
            check_payment.message_post(
                body='Cheque %s (de CUIT %s) migrado desde v13 pero al no estar en mano y tener fecha de pago anterior '
                'a los 60 dias, se migra como un pago normal para minimizar cambios en la base. Información de operaciones:<br/><ul>%s</ul>' % (
                    check_number, check_owner_vat, ''.join(check_data)))
    msj_check_script = {}
    # suffix = 'CH-'
    if not_on_menu:
        # suffix += str(len(not_on_menu))
        msj_check_script['no_payment_not_on_hand'] = not_on_menu
    if not_on_menu_on_hand:
        # suffix += str(len(not_on_menu_on_hand))
        msj_check_script['no_payment_on_hand'] = not_on_menu_on_hand
    if msj_check_script:
        env['ir.config_parameter'].sudo().set_param('upgrade_l10n_latam_check_warning' , msj_check_script)

@openupgrade.migrate()
def migrate(env, version):
    adapt_journals(env)
    adapt_third_checks(env)
    adapt_own_checks(env)
