"""Tell the customer which tasks stop counting as closed in the jump to 20.0.

``project_ux`` used to redefine ``project.task.is_closed`` as ``stage_id.fold``: a task
parked in a folded kanban column counted as closed. From 20.0 the field goes back to the
core definition, so a task is closed only when its state is Done or Cancelled.

Nothing moves: the field was a related without store and never had a column. What changes
is the meaning of what is already stored, and that is invisible until somebody opens the
Open/Closed filters and sees other tasks than before. Two groups are worth telling apart:

* a task in a stage that already declares a closing state is finished, and only its state
  stayed open. It reads as open after the jump and somebody has to close it;
* the rest are the tasks the change corrects: parked in Stand by or similar, reported as
  closed while still pending.

Saved filters that search ``is_closed`` are reported too: they keep working and start
answering a different question.

Nothing is written on the customer's data. Which tasks to close, and whether to close them
at all, is the customer's call and is reviewed per database (task 76399).
"""

import logging

from odoo.tools import SQL
from odoo.upgrade import util

from oba import add_customer_note

_logger = logging.getLogger(__name__)

# What the core counts as closed, so what a stage has to declare to close its task.
CLOSED_STATES = ("1_done", "1_canceled")

# A note nobody reads is a note nobody acts on: the total carries the size, the sample the
# shape.
SAMPLE = 50

# Translated names are jsonb; en_US is the value Odoo always writes, the rest is a fallback
# for a record that only ever had another language.
NAME = "COALESCE(%(table)s.name ->> 'en_US', (SELECT value FROM jsonb_each_text(%(table)s.name) LIMIT 1))"

TASKS_IN_FOLDED_STAGES = SQL(
    """
    SELECT t.id,
           t.name,
           {stage_name} AS stage_name,
           {project_name} AS project_name,
           s.task_state
      FROM project_task t
      JOIN project_task_type s ON s.id = t.stage_id
 LEFT JOIN project_project p ON p.id = t.project_id
     WHERE s.fold IS TRUE
       AND t.active IS TRUE
       AND t.state NOT IN %(closed)s
  ORDER BY t.id
    """.format(
        stage_name=NAME % {"table": "s"},
        project_name=NAME % {"table": "p"},
    ),
    closed=CLOSED_STATES,
)

# Stages are per project, so the same name comes back once per column that carries it.
# Grouped, the customer reads "Done, 3 columns" instead of Done three times.
FOLDED_STAGES_WITHOUT_CLOSING_STATE = SQL(
    """
    SELECT {stage_name} AS stage_name, count(*) AS columns
      FROM project_task_type s
     WHERE s.fold IS TRUE
       AND (s.task_state IS NULL OR s.task_state NOT IN %(closed)s)
  GROUP BY stage_name
  ORDER BY stage_name
    """.format(stage_name=NAME % {"table": "s"}),
    closed=CLOSED_STATES,
)

FILTERS_SEARCHING_IS_CLOSED = SQL(
    """
    SELECT name
      FROM ir_filters
     WHERE model_id = 'project.task'
       AND active IS TRUE
       AND domain LIKE %(pattern)s
  ORDER BY name
    """,
    pattern="%is_closed%",
)


def _task(row):
    task_id, name, stage_name, project_name, __ = row
    return {"id": task_id, "tarea": name, "etapa": stage_name, "proyecto": project_name}


def migrate(cr, version):
    if not util.module_installed(cr, "project_ux"):
        return

    cr.execute(TASKS_IN_FOLDED_STAGES)
    rows = cr.fetchall()
    # The stage already says what state closes it, so the task is finished and its state
    # stayed behind. These are the ones somebody has to close.
    to_close = [row for row in rows if row[4] in CLOSED_STATES]
    corrected = len(rows) - len(to_close)

    cr.execute(FOLDED_STAGES_WITHOUT_CLOSING_STATE)
    stages = [{"etapa": name, "columnas": columns} for name, columns in cr.fetchall()]

    cr.execute(FILTERS_SEARCHING_IS_CLOSED)
    filters = [name for (name,) in cr.fetchall()]

    _logger.info(
        "project_ux: %s tasks in folded stages stop counting as closed (%s of them already "
        "finished), %s folded stages do not close their task, %s saved filters search is_closed",
        len(rows),
        len(to_close),
        len(stages),
        len(filters),
    )

    # Emitted even when everything is empty: "nothing was left pending" is a result the
    # message may want to say, and the row is what lets it.
    add_customer_note(
        cr,
        {
            "project_ux_tareas_a_cerrar_total": len(to_close),
            "project_ux_tareas_a_cerrar": [_task(row) for row in to_close[:SAMPLE]],
            "project_ux_tareas_que_pasan_a_abiertas_total": corrected,
            "project_ux_etapas_plegadas_sin_cierre": stages[:SAMPLE],
            "project_ux_filtros_guardados_con_is_closed": filters[:SAMPLE],
        },
    )
