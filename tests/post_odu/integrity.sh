#!/bin/bash
# Invariants (IntegrityCase of odoo.upgrade.testing) that live in modules/<module>/tests/.
#
#   integrity.sh prepare <db> [odoo args]   source database, before it goes to Odoo
#   integrity.sh copy <from_db> <to_db>     values the target lacks, from another database
#   integrity.sh check <db> [odoo args]     upgraded database, after our -u
#
# The odoo command comes from ODOO_BIN (default: odoo). Exit 1 when an invariant fails, and
# also when one has no value saved: Odoo skips it with an INFO line and leaves it green.
set -o pipefail

ROOT=$(cd "$(dirname "$0")/../.." && pwd)
TABLE=upgrade_test_data
read -ra ODOO <<< "${ODOO_BIN:-odoo}"

run_tests() {
    local phase=$1 db=$2
    shift 2
    "${ODOO[@]}" -d "$db" --upgrade-path="$ROOT/modules" --test-tags "integrity_case.test_$phase" \
        --stop-after-init --log-handler=odoo.upgrade.testing:INFO "$@"
}

case $1 in
prepare)
    run_tests prepare "${@:2}"
    ;;
copy)
    # Only the missing keys: a value already there was taken before the pass and wins
    psql -d "$3" -v ON_ERROR_STOP=1 -q \
        -c "CREATE TABLE IF NOT EXISTS $TABLE (key varchar(255) PRIMARY KEY, class varchar, value jsonb NOT NULL)" \
        -c "CREATE TEMP TABLE source_values (LIKE $TABLE)" \
        -c "\\copy source_values FROM PROGRAM 'psql -d $2 -Atc \"COPY $TABLE (key, class, value) TO STDOUT\"'" \
        -c "INSERT INTO $TABLE SELECT * FROM source_values ON CONFLICT (key) DO NOTHING"
    ;;
check)
    log=$(mktemp)
    trap 'rm -f "$log"' EXIT
    run_tests check "${@:2}" 2>&1 | tee "$log"
    status=$?
    if grep -q "No value found for" "$log"; then
        echo "=== integrity: FAIL - invariants without a value, so nothing was compared ==="
        grep -o "No value found for [^,]*" "$log"
        status=1
    fi
    exit $status
    ;;
*)
    echo "usage: $0 prepare <db> | copy <from_db> <to_db> | check <db>" >&2
    exit 2
    ;;
esac
