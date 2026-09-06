#!/usr/bin/env bash
set -euo pipefail

MODE="${1:---check}"
BIN_DIR="${HOME}/.local/bin"

log() { printf '%s\n' "$*"; }
has() { command -v "$1" >/dev/null 2>&1; }

install_npm() {
	local pkg="$1"
	if npm list -g --depth=0 "${pkg}" >/dev/null 2>&1; then
		log "present npm: ${pkg}"
	else
		if [ "${MODE}" = "--install" ]; then
			npm install -g "${pkg}" --no-fund --no-audit
		else
			log "would install npm: ${pkg}"
		fi
	fi
}

install_pipx() {
	local pkg="$1" bin="$2"
	if has "${bin}"; then
		log "present pipx: ${pkg}"
	else
		if [ "${MODE}" = "--install" ]; then
			pipx install "${pkg}"
		else
			log "would install pipx: ${pkg}"
		fi
	fi
}

install_release_binary() {
	local repo="$1" asset_regex="$2" bin="$3" checksum_regex="${4:-}"
	if has "${bin}"; then
		log "present release binary: ${bin}"
		return 0
	fi
	if [ "${MODE}" != "--install" ]; then
		log "would install release binary: ${bin} (${repo})"
		return 0
	fi
	mkdir -p "${BIN_DIR}"
	local tmp
	tmp="$(mktemp -d)"
	trap 'rm -rf "${tmp}"' RETURN
	gh api "repos/${repo}/releases/latest" >"${tmp}/release.json"
	local asset_url asset_name
	asset_url="$(jq -r --arg re "${asset_regex}" '.assets[] | select(.name|test($re)) | .browser_download_url' "${tmp}/release.json" | head -n 1)"
	asset_name="$(basename "${asset_url}")"
	curl -fsSL "${asset_url}" -o "${tmp}/${asset_name}"
	if [ -n "${checksum_regex}" ]; then
		local sum_url sum_name
		sum_url="$(jq -r --arg re "${checksum_regex}" '.assets[] | select(.name|test($re)) | .browser_download_url' "${tmp}/release.json" | head -n 1)"
		sum_name="$(basename "${sum_url}")"
		curl -fsSL "${sum_url}" -o "${tmp}/${sum_name}"
		(cd "${tmp}" && grep "  ${asset_name}$" "${sum_name}" | sha256sum -c -)
	fi
	if [[ "${asset_name}" == *.tar.gz ]]; then
		tar -xzf "${tmp}/${asset_name}" -C "${tmp}"
		install -m 0755 "$(find "${tmp}" -maxdepth 2 -type f -name "${bin}" | head -n 1)" "${BIN_DIR}/${bin}"
	elif [[ "${asset_name}" == *.gz ]]; then
		gzip -dc "${tmp}/${asset_name}" >"${BIN_DIR}/${bin}"
		chmod 0755 "${BIN_DIR}/${bin}"
	else
		log "unsupported asset type: ${asset_name}"
		return 1
	fi
}

case "${MODE}" in
--dry-run | --check | --install) ;;
*)
	log "usage: $0 [--dry-run|--check|--install]"
	exit 2
	;;
esac

log "mode=${MODE}"

install_npm "@playwright/mcp@0.0.80"
install_npm "@upstash/context7-mcp@4.0.5"
install_npm "markdownlint-cli2@0.23.2"
install_pipx "semgrep" "semgrep"

install_release_binary "zricethezav/gitleaks" "linux_x64\\.tar\\.gz$" "gitleaks" "_checksums\\.txt$"
install_release_binary "aquasecurity/trivy" "Linux-64bit\\.tar\\.gz$" "trivy" "_checksums\\.txt$"
install_release_binary "anchore/syft" "linux_amd64\\.tar\\.gz$" "syft" "_checksums\\.txt$"
install_release_binary "anchore/grype" "linux_amd64\\.tar\\.gz$" "grype" "_checksums\\.txt$"
install_release_binary "tamasfe/taplo" "taplo-linux-x86_64\\.gz$" "taplo"

if has actionlint; then
	log "present go install: actionlint"
elif [ "${MODE}" = "--install" ] && has go; then
	GOBIN="${BIN_DIR}" go install github.com/rhysd/actionlint/cmd/actionlint@latest
else
	log "would install go tool: actionlint"
fi

for c in codebase-memory-mcp semgrep gitleaks trivy syft grype actionlint markdownlint-cli2 taplo; do
	if has "${c}"; then
		log "ok: ${c}"
	else
		log "missing: ${c}"
	fi
done
