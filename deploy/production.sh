#!/usr/bin/env bash
# Called over SSH by the manually dispatched production workflow.
set -euo pipefail
umask 077

revision="${1:-}"
[[ "$revision" =~ ^[0-9a-f]{40}$ ]] || { echo 'Expected an exact 40-character Git commit SHA.' >&2; exit 2; }

app_dir="${D2L_APP_DIR:-/home/blakepowell/app}"
app_python="${D2L_APP_PYTHON:-/home/blakepowell/venv312/bin/python}"
uv_bin="${D2L_UV_BIN:-/home/blakepowell/python-upgrade-tools/bin/uv}"
state_dir="${D2L_DEPLOY_STATE_DIR:-/home/blakepowell/deploy-state}"
health_url="${D2L_HEALTH_URL:-https://direct2logbook.com/accounts/login/}"

mkdir -p "$state_dir"
chmod 700 "$state_dir"
exec 9>"$state_dir/deploy.lock"
flock -n 9 || { echo 'Another deployment is running.' >&2; exit 1; }

cd "$app_dir"
[[ -x "$app_python" && -x "$uv_bin" ]] || { echo 'Application Python or deployment uv is missing.' >&2; exit 1; }
[[ "$("$uv_bin" --version)" == 'uv 0.13.6'* ]] || { echo 'Deployment requires uv 0.13.6 in python-upgrade-tools.' >&2; exit 1; }
[[ "$(git symbolic-ref --short HEAD)" == master ]] || { echo 'Production checkout must be on master.' >&2; exit 1; }
git diff --quiet
git diff --cached --quiet
[[ -z "$(git ls-files --others --exclude-standard)" ]] || { echo 'Untracked files must be reviewed before deployment.' >&2; exit 1; }
git fetch origin master
[[ "$(git rev-parse origin/master)" == "$revision" ]] || { echo 'Master advanced; run a new deployment for its latest commit.' >&2; exit 1; }
git merge-base --is-ancestor HEAD "$revision"
previous="$(git rev-parse HEAD)"
printf 'previous=%s\ntarget=%s\n' "$previous" "$revision" > "$state_dir/last-attempt"

# No runtime mutation until a fresh, off-server backup passes verification.
"$app_python" manage.py backup_database

stopped=false
on_exit() {
  result=$?
  if (( result != 0 )); then
    echo "Deployment failed. Previous revision: $previous. Inspect logs and $state_dir/last-attempt." >&2
    if [[ "$stopped" == true ]]; then
      sudo -n /usr/bin/supervisorctl stop logbook celery || true
      echo 'Services are stopped. Repair or perform a reviewed rollback before starting them.' >&2
    fi
  fi
}
trap on_exit EXIT

# A short maintenance window avoids serving code against changing dependencies/schema.
stopped=true
sudo -n /usr/bin/supervisorctl stop logbook celery
git merge --ff-only "$revision"
"$uv_bin" pip sync --python "$app_python" requirements.txt
"$uv_bin" pip check --python "$app_python"
"$app_python" -m pip check
"$app_python" manage.py check
"$app_python" manage.py migrate --plan
"$app_python" manage.py migrate --noinput
"$app_python" manage.py collectstatic --noinput
sudo -n /usr/bin/supervisorctl start logbook celery
status="$(sudo -n /usr/bin/supervisorctl status logbook celery)"
printf '%s\n' "$status"
[[ "$status" =~ logbook[[:space:]]+RUNNING && "$status" =~ celery[[:space:]]+RUNNING ]]
curl --fail --silent --show-error --location --max-time 15 --retry 4 \
  --retry-delay 3 --retry-connrefused --retry-all-errors "$health_url" > /dev/null
stopped=false
printf 'previous=%s\ndeployed=%s\n' "$previous" "$revision" > "$state_dir/last-success"
echo "Deployment healthy: $revision"
