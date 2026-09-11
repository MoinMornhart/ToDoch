#!/usr/bin/env bash
# Todoch – Proxmox VE LXC Quickstart (im Stil der community-scripts)
#
#   Installation – in der Shell des Proxmox-Hosts (als root):
#     bash -c "$(curl -fsSL https://raw.githubusercontent.com/MoinMornhart/Todoch/main/ct/todoch.sh)"
#
#   Update – in der Konsole des Containers:
#     update
#
# Copyright (c) 2026 MoinMornhart | Lizenz: MIT | https://github.com/MoinMornhart/Todoch

REPO="${REPO:-MoinMornhart/Todoch}"
TODOCH_BRANCH="${TODOCH_BRANCH:-$(cat /etc/todoch/branch 2>/dev/null || echo main)}"
REPO_RAW="${REPO_RAW:-https://raw.githubusercontent.com/${REPO}/${TODOCH_BRANCH}}"
source <(curl -fsSL -H "Accept: application/vnd.github.raw" \
  "https://api.github.com/repos/${REPO}/contents/deploy/lxc/build.func?ref=${TODOCH_BRANCH}" 2>/dev/null ||
  curl -fsSL "${REPO_RAW}/deploy/lxc/build.func?t=$(date +%s)")
if ! declare -F start >/dev/null; then
  echo "Todoch-Skripte konnten nicht von GitHub geladen werden (Internetverbindung?)." >&2
  exit 1
fi

APP="Todoch"
var_tags="${var_tags:-todo;kalender;productivity}"
var_cpu="${var_cpu:-2}"
var_ram="${var_ram:-2048}"
var_disk="${var_disk:-16}"
var_os="${var_os:-debian}"
var_version="${var_version:-13}"
var_unprivileged="${var_unprivileged:-1}"

color
header_info "$APP"
variables
catch_errors

function update_script() {
  todoch_update
}

start
build_container
description
show_summary
