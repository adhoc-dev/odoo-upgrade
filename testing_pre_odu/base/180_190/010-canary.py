NAME = "upgrade-prepare-demo canary"


def migrate(env):
    if not env["res.partner"].search([("name", "=", NAME)], limit=1):
        env["res.partner"].create({"name": NAME})
