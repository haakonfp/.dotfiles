#!/usr/bin/env bash
# Install the pinned Mono family for this Linux user; optionally install on WSL's host.
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: scripts/install-fonts.sh [--dry-run] [--windows]
  Default: install Linux per-user fonts and refresh the font cache.
  --windows: also call windows/Install-Fonts.ps1 on the Windows host via WSL.
  --dry-run: describe the work without downloads, writes or host commands.
Requires curl, sha256sum, tar/xz, find, fontconfig; --windows needs WSL interop.
EOF
}

dry_run=false
windows=false
for arg in "$@"; do
  case "$arg" in
    --dry-run) dry_run=true ;;
    --windows) windows=true ;;
    -h|--help) usage; exit 0 ;;
    *) printf 'Unknown font option: %s\n' "$arg" >&2; usage >&2; exit 2 ;;
  esac
done

version=3.5.1
url="https://github.com/ryanoasis/nerd-fonts/releases/download/v${version}/JetBrainsMono.tar.xz"
# Official release asset digest, verified 2026-11-06:
# https://github.com/ryanoasis/nerd-fonts/releases/expanded_assets/v3.5.1
# The release also publishes SHA-256.txt (sha256 e03d7ad54547d83f1620719cbc89b5684bc0c6fb028160640aa322b5035a63fb).
sha256=04d5e8f903693f9dd13e16f867e994834e681eb3c72c0d337a770dcda09010cf
destination="$HOME/.local/share/fonts/jetbrains-mono-nerd"
styles=(Thin ThinItalic ExtraLight ExtraLightItalic Light LightItalic Regular Italic
        Medium MediumItalic SemiBold SemiBoldItalic Bold BoldItalic ExtraBold ExtraBoldItalic)

if $dry_run; then
  printf 'Would verify Nerd Fonts %s archive %s (SHA256 %s).\n' "$version" "$url" "$sha256"
  printf 'Would install 16 JetBrainsMono Nerd Font Mono variants and upstream license to %s; refresh Linux font cache.\n' "$destination"
  if $windows; then
    printf 'Would install/register the same family for the Windows user using windows/Install-Fonts.ps1 via wslpath and powershell.exe.\n'
  fi
  exit 0
fi

# Preflight host interop before starting a potentially long Linux download.
if $windows; then
  for command in wslpath powershell.exe; do
    command -v "$command" >/dev/null || { printf '%s is required for --windows; run from WSL with interop enabled.\n' "$command" >&2; exit 1; }
  done
fi
for command in curl sha256sum tar find fc-cache; do
  command -v "$command" >/dev/null || { printf 'Required font installer command missing: %s\n' "$command" >&2; exit 1; }
done

complete=true
if [[ ! -f "$destination/.nerd-fonts-version" || ! -f "$destination/OFL.txt" ]] ||
   [[ "$(cat "$destination/.nerd-fonts-version" 2>/dev/null || true)" != "$version $sha256" ]]; then
  complete=false
fi
for style in "${styles[@]}"; do
  [[ -s "$destination/JetBrainsMonoNerdFontMono-${style}.ttf" ]] || complete=false
done

if $complete; then
  printf 'Linux JetBrainsMono Nerd Font Mono %s already installed.\n' "$version"
else
  staging=$(mktemp -d)
  trap 'rm -rf -- "$staging"' EXIT
  curl --fail --location --retry 3 --output "$staging/JetBrainsMono.tar.xz" "$url"
  printf '%s  %s\n' "$sha256" "$staging/JetBrainsMono.tar.xz" | sha256sum --check --status || {
    printf 'Font archive checksum mismatch; no fonts installed.\n' >&2; exit 1;
  }
  mkdir "$staging/unpacked"
  tar --extract --xz --file "$staging/JetBrainsMono.tar.xz" --directory "$staging/unpacked" --no-same-owner --no-same-permissions
  fonts=()
  for style in "${styles[@]}"; do
    matches=()
    mapfile -d '' -t matches < <(find "$staging/unpacked" -type f -name "JetBrainsMonoNerdFontMono-${style}.ttf" -print0)
    if [[ ${#matches[@]} != 1 || ! -s "${matches[0]:-}" ]]; then
      printf 'Archive lacks a unique Mono %s variant; no fonts installed.\n' "$style" >&2; exit 1
    fi
    fonts+=("${matches[0]}")
  done
  licenses=()
  mapfile -d '' -t licenses < <(find "$staging/unpacked" -type f -iname 'OFL.txt' -print0)
  if [[ ${#licenses[@]} == 0 ]]; then
    printf 'Archive lacks upstream OFL.txt; no fonts installed.\n' >&2; exit 1
  fi
  mkdir -p "$destination"
  for font in "${fonts[@]}"; do
    install -m 644 "$font" "$destination/"
  done
  install -m 644 "${licenses[0]}" "$destination/OFL.txt"
  # Keep upstream icon-license attribution alongside the font license if supplied.
  while IFS= read -r -d '' readme; do
    install -m 644 "$readme" "$destination/README-upstream.md"
    break
  done < <(find "$staging/unpacked" -type f -name 'README.md' -print0)
  fc-cache -f "$destination"
  printf '%s %s\n' "$version" "$sha256" > "$destination/.nerd-fonts-version"
  printf 'Installed all 16 Mono variants and upstream license to %s.\n' "$destination"
fi

if $windows; then
  script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
  host_script=$(wslpath -w "$script_dir/../windows/Install-Fonts.ps1")
  host_source=$(wslpath -w "$destination")
  powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "$host_script" -SourceDirectory "$host_source"
else
  printf 'On WSL, also run scripts/install-fonts.sh --windows to install the host font for Windows Terminal.\n'
fi
