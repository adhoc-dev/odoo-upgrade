#!/usr/bin/env python3
"""Frena el PR si un script de modules/ no tiene su check (ADR 0037 de
actua-20), sin levantar Odoo. Lo corre el job missing-checks de layout.yml;
check_expected.py hace lo mismo en runbot, pero solo para el salto que prueba.

    python3 tests/post_odu/missing_checks.py
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import expected_lib as X  # noqa: E402

root = os.path.join(os.path.dirname(os.path.dirname(HERE)), "modules")
problems = [p for tag in X.enforced_tags(root) for p in X.missing_checks(root, tag)]
for p in problems:
    print("::error::%s" % p)
if problems:
    print("%s script(s) sin su check: cada uno lleva su expected, o NO_CHECK con el "
          "motivo (tests/post_odu/README.md)" % len(problems))
    sys.exit(1)
print("Todo script desde el salto a %s tiene su check o su NO_CHECK" % X.FIRST_ENFORCED)
