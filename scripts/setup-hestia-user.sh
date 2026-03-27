#!/usr/bin/env bash
# setup-hestia-user.sh
# Creates the _hestia service user and _hestia_svc group on the Mac Mini,
# then sets file permissions for the Hestia application directory.
# Must be run as root (sudo).
#
# Usage: sudo bash scripts/setup-hestia-user.sh

set -euo pipefail

# ---------------------------------------------------------------------------
# Color output
# ---------------------------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

info()    { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*" >&2; }
die()     { error "$*"; exit 1; }

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
HESTIA_USER="andrewroman117"
HESTIA_HOME="/Users/${HESTIA_USER}"
HESTIA_DIR="${HESTIA_HOME}/hestia"

SERVICE_USER="_hestia"
SERVICE_GROUP="_hestia_svc"

UID_MIN=300
UID_MAX=400
GID_MIN=300
GID_MAX=400

# ---------------------------------------------------------------------------
# Root check
# ---------------------------------------------------------------------------
if [[ "${EUID}" -ne 0 ]]; then
    die "This script must be run as root. Use: sudo bash $0"
fi

# ---------------------------------------------------------------------------
# Helper: find an unused UID in range
# ---------------------------------------------------------------------------
find_free_uid() {
    local min="${1}" max="${2}"
    for candidate in $(seq "${min}" "${max}"); do
        if ! dscl . -list /Users UniqueID | awk '{print $2}' | grep -qx "${candidate}"; then
            echo "${candidate}"
            return 0
        fi
    done
    die "No free UID found in range ${min}-${max}"
}

# ---------------------------------------------------------------------------
# Helper: find an unused GID in range
# ---------------------------------------------------------------------------
find_free_gid() {
    local min="${1}" max="${2}"
    for candidate in $(seq "${min}" "${max}"); do
        if ! dscl . -list /Groups PrimaryGroupID | awk '{print $2}' | grep -qx "${candidate}"; then
            echo "${candidate}"
            return 0
        fi
    done
    die "No free GID found in range ${min}-${max}"
}

# ---------------------------------------------------------------------------
# 1. Create the _hestia system user
# ---------------------------------------------------------------------------
info "Checking for service user '${SERVICE_USER}'..."

if dscl . -read "/Users/${SERVICE_USER}" > /dev/null 2>&1; then
    warn "User '${SERVICE_USER}' already exists — skipping creation."
else
    NEW_UID="$(find_free_uid "${UID_MIN}" "${UID_MAX}")"
    info "Creating user '${SERVICE_USER}' with UID ${NEW_UID}..."

    dscl . -create "/Users/${SERVICE_USER}"
    dscl . -create "/Users/${SERVICE_USER}" UserShell /usr/bin/false
    dscl . -create "/Users/${SERVICE_USER}" RealName "Hestia Service Account"
    dscl . -create "/Users/${SERVICE_USER}" UniqueID "${NEW_UID}"
    dscl . -create "/Users/${SERVICE_USER}" NFSHomeDirectory /var/empty
    dscl . -create "/Users/${SERVICE_USER}" IsHidden 1

    info "User '${SERVICE_USER}' created with UID ${NEW_UID}."
fi

# ---------------------------------------------------------------------------
# 2. Create the _hestia_svc group and add members
# ---------------------------------------------------------------------------
info "Checking for service group '${SERVICE_GROUP}'..."

if dscl . -read "/Groups/${SERVICE_GROUP}" > /dev/null 2>&1; then
    warn "Group '${SERVICE_GROUP}' already exists — skipping creation."
else
    NEW_GID="$(find_free_gid "${GID_MIN}" "${GID_MAX}")"
    info "Creating group '${SERVICE_GROUP}' with GID ${NEW_GID}..."

    dscl . -create "/Groups/${SERVICE_GROUP}"
    dscl . -create "/Groups/${SERVICE_GROUP}" PrimaryGroupID "${NEW_GID}"
    dscl . -create "/Groups/${SERVICE_GROUP}" RealName "Hestia Service Group"

    info "Group '${SERVICE_GROUP}' created with GID ${NEW_GID}."
fi

# Ensure both members belong to the group (idempotent)
for member in "${SERVICE_USER}" "${HESTIA_USER}"; do
    if dscl . -read "/Groups/${SERVICE_GROUP}" GroupMembership 2>/dev/null \
            | grep -qw "${member}"; then
        warn "User '${member}' is already a member of '${SERVICE_GROUP}' — skipping."
    else
        info "Adding '${member}' to group '${SERVICE_GROUP}'..."
        dscl . -append "/Groups/${SERVICE_GROUP}" GroupMembership "${member}"
    fi
done

# ---------------------------------------------------------------------------
# 3. Verify required directories / files exist before chowning
# ---------------------------------------------------------------------------
ensure_dir() {
    local dir="$1"
    if [[ ! -d "${dir}" ]]; then
        warn "Directory '${dir}' does not exist — creating it."
        mkdir -p "${dir}"
    fi
}

ensure_file() {
    local file="$1"
    if [[ ! -f "${file}" ]]; then
        warn "File '${file}' does not exist — creating placeholder (mode 440)."
        mkdir -p "$(dirname "${file}")"
        touch "${file}"
    fi
}

ensure_dir "${HESTIA_DIR}/hestia"
ensure_dir "${HESTIA_DIR}/.venv"
ensure_dir "${HESTIA_DIR}/data"
ensure_dir "${HESTIA_DIR}/logs"
ensure_dir "${HESTIA_DIR}/config"
ensure_dir "${HESTIA_DIR}/certs"
ensure_file "${HESTIA_HOME}/.hestia/coinbase-credentials"

# ---------------------------------------------------------------------------
# 4. Set file permissions
# ---------------------------------------------------------------------------
info "Applying file ownership and permissions..."

# Application code — owned by andrewroman117:_hestia_svc, chmod 750
# _hestia can read/execute but not write
for app_path in "${HESTIA_DIR}/hestia" "${HESTIA_DIR}/.venv"; do
    info "  ${app_path}: ${HESTIA_USER}:${SERVICE_GROUP} 750"
    chown -R "${HESTIA_USER}:${SERVICE_GROUP}" "${app_path}"
    chmod -R 750 "${app_path}"
done

# Runtime data — owned by _hestia:_hestia_svc, chmod 770
# _hestia can read and write; andrewroman117 (group member) can too
for data_path in "${HESTIA_DIR}/data" "${HESTIA_DIR}/logs"; do
    info "  ${data_path}: ${SERVICE_USER}:${SERVICE_GROUP} 770"
    chown -R "${SERVICE_USER}:${SERVICE_GROUP}" "${data_path}"
    chmod -R 770 "${data_path}"
done

# Config — owned by andrewroman117:_hestia_svc, chmod 750
info "  ${HESTIA_DIR}/config: ${HESTIA_USER}:${SERVICE_GROUP} 750"
chown -R "${HESTIA_USER}:${SERVICE_GROUP}" "${HESTIA_DIR}/config"
chmod -R 750 "${HESTIA_DIR}/config"

# Certs — owned by andrewroman117:_hestia_svc, chmod 750
info "  ${HESTIA_DIR}/certs: ${HESTIA_USER}:${SERVICE_GROUP} 750"
chown -R "${HESTIA_USER}:${SERVICE_GROUP}" "${HESTIA_DIR}/certs"
chmod -R 750 "${HESTIA_DIR}/certs"

# Credential file — owned by andrewroman117:_hestia_svc, chmod 440 (read-only)
CRED_FILE="${HESTIA_HOME}/.hestia/coinbase-credentials"
info "  ${CRED_FILE}: ${HESTIA_USER}:${SERVICE_GROUP} 440"
chown "${HESTIA_USER}:${SERVICE_GROUP}" "${CRED_FILE}"
chmod 440 "${CRED_FILE}"

# ---------------------------------------------------------------------------
# 5. Summary
# ---------------------------------------------------------------------------
info "------------------------------------------------------------"
info "Service user / group setup complete."
info ""
info "  Service user : ${SERVICE_USER}"
info "  Service group: ${SERVICE_GROUP} (members: ${SERVICE_USER}, ${HESTIA_USER})"
info "------------------------------------------------------------"

# ---------------------------------------------------------------------------
# 6. Credential migration instructions
# ---------------------------------------------------------------------------
echo ""
echo -e "${YELLOW}========================================================${NC}"
echo -e "${YELLOW}  Credential Migration — Move .env → macOS Keychain${NC}"
echo -e "${YELLOW}========================================================${NC}"
echo ""
echo "Step 1 — Import each secret from your .env into the Keychain:"
echo ""
echo "  # For each KEY=VALUE pair in ~/.hestia/.env (or ~/hestia/.env):"
echo "  security add-generic-password \\"
echo "      -a \"hestia\" \\"
echo "      -s \"COINBASE_API_KEY\" \\"
echo "      -w \"<your-api-key-value>\" \\"
echo "      -U"
echo ""
echo "  security add-generic-password \\"
echo "      -a \"hestia\" \\"
echo "      -s \"COINBASE_API_SECRET\" \\"
echo "      -w \"<your-api-secret-value>\" \\"
echo "      -U"
echo ""
echo "  # Repeat for every secret in the .env file."
echo ""
echo "Step 2 — Verify the cloud manager can read from the Keychain:"
echo ""
echo "  # Read a secret back (should print the value):"
echo "  security find-generic-password -a \"hestia\" -s \"COINBASE_API_KEY\" -w"
echo ""
echo "  # Verify the Hestia service reads the same value at runtime:"
echo "  sudo -u ${SERVICE_USER} security find-generic-password \\"
echo "      -a \"hestia\" -s \"COINBASE_API_KEY\" -w"
echo ""
echo "  # If the service cannot read it, grant access in Keychain Access.app:"
echo "  # Lock & unlock the login keychain, then set 'Allow all applications'"
echo "  # on each Hestia entry, or whitelist /usr/bin/security explicitly."
echo ""
echo "Step 3 — Remove the plaintext .env after verification:"
echo ""
echo "  # Confirm Hestia is running correctly from Keychain first, then:"
echo "  shred -u ~/.hestia/.env   # or: rm -P ~/.hestia/.env  (macOS)"
echo "  # Also remove any .env copies:"
echo "  find ~/hestia -name '.env' -maxdepth 3 -print"
echo ""
echo -e "${GREEN}All done. Hestia service user environment is hardened.${NC}"
