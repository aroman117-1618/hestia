#!/bin/bash
# Generate self-signed SSL certificate for Hestia API
#
# This creates a certificate valid for:
# - localhost (development)
# - hestia-mini (local network)
# - *.tail*.ts.net (Tailscale MagicDNS)
#
# Security features:
# - 4096-bit RSA key (industry standard for high security)
# - Password-protected private key (stored in macOS Keychain)
# - SHA-256 signature algorithm
# - Key Usage and Extended Key Usage extensions
# - Certificate fingerprint output for pinning
#
# Usage: ./scripts/generate-cert.sh [hostname]
# Example: ./scripts/generate-cert.sh hestia-mini.tail12345.ts.net

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
CERT_DIR="$PROJECT_DIR/certs"

# Configuration
CERT_FILE="$CERT_DIR/hestia.crt"
KEY_FILE="$CERT_DIR/hestia.key"
DAYS_VALID=365
KEY_SIZE=4096
KEYCHAIN_SERVICE="hestia-ssl-key"
KEYCHAIN_ACCOUNT="hestia"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Get hostname from argument or prompt
TAILSCALE_HOST="${1:-}"
if [ -z "$TAILSCALE_HOST" ]; then
    echo "Enter your Tailscale hostname (e.g., hestia-mini.tail12345.ts.net)"
    echo "Or press Enter to skip Tailscale DNS:"
    read -r TAILSCALE_HOST
fi

# Create certs directory if it doesn't exist
mkdir -p "$CERT_DIR"

# Build Subject Alternative Names
SAN="DNS:localhost,DNS:hestia-mini,DNS:hestia-mini.local,IP:127.0.0.1"
if [ -n "$TAILSCALE_HOST" ]; then
    SAN="$SAN,DNS:$TAILSCALE_HOST"
    log_info "Including Tailscale hostname: $TAILSCALE_HOST"
fi

echo ""
log_info "Generating self-signed certificate..."
echo "  Certificate: $CERT_FILE"
echo "  Private key: $KEY_FILE"
echo "  Key size: $KEY_SIZE bits"
echo "  Valid for: $DAYS_VALID days"
echo "  SANs: $SAN"
echo ""

# Generate random passphrase and store in Keychain
log_info "Generating secure passphrase..."
PASSPHRASE=$(openssl rand -base64 32)

# Store passphrase in macOS Keychain
# First, try to delete any existing entry
security delete-generic-password -s "$KEYCHAIN_SERVICE" -a "$KEYCHAIN_ACCOUNT" 2>/dev/null || true

# Add new passphrase to Keychain
if security add-generic-password -s "$KEYCHAIN_SERVICE" -a "$KEYCHAIN_ACCOUNT" -w "$PASSPHRASE" 2>/dev/null; then
    log_info "Passphrase stored in macOS Keychain"
    KEY_ENCRYPTED=true
else
    log_warn "Failed to store passphrase in Keychain. Generating unencrypted key."
    log_warn "This is less secure. Consider running with appropriate Keychain access."
    KEY_ENCRYPTED=false
fi

# Create temporary OpenSSL config file for extensions
OPENSSL_CNF=$(mktemp)
cat > "$OPENSSL_CNF" << EOF
[req]
distinguished_name = req_distinguished_name
x509_extensions = v3_req
prompt = no

[req_distinguished_name]
CN = Hestia API
O = Hestia
C = US

[v3_req]
basicConstraints = CA:FALSE
keyUsage = critical, digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth, clientAuth
subjectAltName = $SAN
EOF

# Generate private key and certificate
if [ "$KEY_ENCRYPTED" = true ]; then
    # Generate encrypted private key
    openssl req -x509 \
        -newkey rsa:$KEY_SIZE \
        -keyout "$KEY_FILE" \
        -out "$CERT_FILE" \
        -days $DAYS_VALID \
        -sha256 \
        -passout pass:"$PASSPHRASE" \
        -config "$OPENSSL_CNF" \
        -extensions v3_req \
        2>/dev/null

    # Verify the key is actually encrypted
    if grep -q "ENCRYPTED" "$KEY_FILE"; then
        log_info "Private key is encrypted"
    else
        log_warn "Private key encryption verification failed"
    fi
else
    # Generate unencrypted key (fallback)
    openssl req -x509 \
        -newkey rsa:$KEY_SIZE \
        -keyout "$KEY_FILE" \
        -out "$CERT_FILE" \
        -days $DAYS_VALID \
        -sha256 \
        -nodes \
        -config "$OPENSSL_CNF" \
        -extensions v3_req \
        2>/dev/null
fi

# Clean up temp file
rm -f "$OPENSSL_CNF"

# Set restrictive permissions on key
chmod 600 "$KEY_FILE"
chmod 644 "$CERT_FILE"

# Verify the certificate
log_info "Verifying certificate..."
if openssl x509 -in "$CERT_FILE" -noout -text 2>/dev/null | grep -q "Subject: CN = Hestia API"; then
    log_info "Certificate generated and verified successfully!"
else
    log_error "Certificate verification failed!"
    exit 1
fi

# Display certificate info
echo ""
echo "Certificate Details:"
openssl x509 -in "$CERT_FILE" -noout -subject -dates -ext subjectAltName 2>/dev/null | sed 's/^/  /'

# Calculate certificate fingerprint for pinning
echo ""
log_info "Certificate fingerprint (SHA-256) for pinning:"
FINGERPRINT=$(openssl x509 -in "$CERT_FILE" -noout -fingerprint -sha256 2>/dev/null | cut -d'=' -f2)
echo "  $FINGERPRINT"

# Create fingerprint file for iOS app bundle
FINGERPRINT_FILE="$CERT_DIR/hestia-fingerprint.txt"
echo "$FINGERPRINT" > "$FINGERPRINT_FILE"
log_info "Fingerprint saved to: $FINGERPRINT_FILE"

echo ""
echo "==================================================================="
echo "                       SETUP INSTRUCTIONS"
echo "==================================================================="
echo ""
echo "To trust this certificate on macOS:"
echo "  sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain $CERT_FILE"
echo ""
echo "To trust on iOS:"
echo "  1. AirDrop $CERT_FILE to your device"
echo "  2. Settings > General > VPN & Device Management > Install"
echo "  3. Settings > General > About > Certificate Trust Settings > Enable"
echo ""

if [ "$KEY_ENCRYPTED" = true ]; then
    echo "To start Hestia with HTTPS (encrypted key):"
    echo "  The server will automatically retrieve the passphrase from Keychain."
    echo ""
    echo "  Set environment variables:"
    echo "    export HESTIA_SSL_CERT=$CERT_FILE"
    echo "    export HESTIA_SSL_KEY=$KEY_FILE"
    echo "    python -m hestia.api.server"
    echo ""
    echo "To manually retrieve the passphrase:"
    echo "  security find-generic-password -s $KEYCHAIN_SERVICE -a $KEYCHAIN_ACCOUNT -w"
else
    echo "To start Hestia with HTTPS:"
    echo "  python -m hestia.api.server --ssl-cert $CERT_FILE --ssl-key $KEY_FILE"
    echo ""
    echo "Or set environment variables:"
    echo "  export HESTIA_SSL_CERT=$CERT_FILE"
    echo "  export HESTIA_SSL_KEY=$KEY_FILE"
    echo "  python -m hestia.api.server"
fi
echo ""
echo "==================================================================="

# Clear passphrase from memory
unset PASSPHRASE
