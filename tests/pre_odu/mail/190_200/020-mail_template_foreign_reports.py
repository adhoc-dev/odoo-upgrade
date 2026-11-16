# Caso de base/0.0.0/end-240-drop_foreign_model_mail_template_reports.py, que
# desvincula de cada plantilla de correo los reportes de otro modelo. Lo verifica
# base/tests/expected_200.py.
#
# POR QUE HAY QUE SEMBRAR: ninguna data de prueba trae una plantilla con un
# reporte de otro modelo. Una plantilla de contactos queda con dos reportes:
# uno de contactos (se queda) y uno de usuarios (se va). Los dos reportes son
# propios, para no depender de los que traiga cada modulo instalado.

TEMPLATE_XMLID = "upgrade_prepare_demo.mail_template_foreign_report"
OWN_REPORT_XMLID = "upgrade_prepare_demo.report_partner_own_model"
FOREIGN_REPORT_XMLID = "upgrade_prepare_demo.report_users_foreign_model"


def migrate(env):
    env["ir.actions.report"]._load_records(
        [
            {
                "xml_id": OWN_REPORT_XMLID,
                "values": {
                    "name": "Reporte de contactos",
                    "model": "res.partner",
                    "report_name": "upgrade_prepare_demo.report_partner",
                },
                "noupdate": True,
            },
            {
                "xml_id": FOREIGN_REPORT_XMLID,
                "values": {
                    "name": "Reporte de usuarios",
                    "model": "res.users",
                    "report_name": "upgrade_prepare_demo.report_users",
                },
                "noupdate": True,
            },
        ]
    )
    reports = env.ref(OWN_REPORT_XMLID) | env.ref(FOREIGN_REPORT_XMLID)
    env["mail.template"]._load_records(
        [
            {
                "xml_id": TEMPLATE_XMLID,
                "values": {
                    "name": "Plantilla con un reporte de otro modelo",
                    "model_id": env["ir.model"]._get_id("res.partner"),
                    "body_html": '<p>Hola <t t-out="object.name"/></p>',
                    "report_template_ids": [(6, 0, reports.ids)],
                },
                "noupdate": True,
            }
        ]
    )
    env.flush_all()
