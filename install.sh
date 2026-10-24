#!/usr/bin/env bash
# Run as the ordinary Raspberry Pi desktop user, not through sudo.
set -Eeuo pipefail
trap 'printf "Installation stopped (line %s). No automatic reboot was requested.\n" "$LINENO" >&2' ERR

repo_url='https://github.com/EpicNori/coscarOS.git'
legacy_repo_url='https://github.com/EpicNori/clean-room-reverse-engeenering-hudiy.git'
install_root="${COSCAROS_INSTALL_DIR:-${HUDIY_INSTALL_DIR:-$HOME/coscarOS}}"
if [[ -z ${COSCAROS_INSTALL_DIR:-} && -z ${HUDIY_INSTALL_DIR:-} && -d "$HOME/hudiy-recreation/.git" ]]; then
    install_root="$HOME/hudiy-recreation"
fi
check_only=false
assume_yes=false
for option in "$@"; do
    case "$option" in
        --check) check_only=true ;;
        --yes) assume_yes=true ;;
        --no-autologin|--skip-hotspot|--skip-black-boot) ;;
        --help|-h)
            printf 'Usage: bash install.sh [--check] [--yes] [--no-autologin] [--skip-hotspot] [--skip-black-boot]\n'
            printf 'Defaults: build our app, prepare an inactive hotspot, enable desktop autologin/startup.\n'
            exit 0 ;;
        *) printf 'Unknown option: %s\n' "$option" >&2; exit 2 ;;
    esac
done
if [[ $EUID -eq 0 ]]; then
    printf 'Run as your desktop user without sudo; individual system steps request sudo.\n' >&2
    exit 1
fi
if [[ $(uname -s) != Linux || $(uname -m) != aarch64 || $(dpkg --print-architecture) != arm64 ]]; then
    printf 'Use 64-bit Raspberry Pi OS Desktop (Bookworm or Trixie).\n' >&2
    exit 1
fi
if [[ ! -r /proc/device-tree/model ]] || ! grep -aq 'Raspberry Pi' /proc/device-tree/model; then
    printf 'This installer targets a Raspberry Pi.\n' >&2; exit 1
fi
# Values come from the installed OS, not a network response.
source /etc/os-release
if [[ ${VERSION_CODENAME:-} != bookworm && ${VERSION_CODENAME:-} != trixie ]]; then
    printf 'Supported OS releases: Bookworm and Trixie.\n' >&2; exit 1
fi
if [[ ! -f /etc/xdg/labwc/rc.xml || ! -x /usr/bin/labwc ]]; then
    printf 'Install Raspberry Pi OS with Desktop; OS Lite is not supported by this installer.\n' >&2
    exit 1
fi
if [[ -L "$install_root" ]]; then
    printf 'Installation directory cannot be a symlink.\n' >&2; exit 1
fi
if ! command -v git >/dev/null || ! command -v python3 >/dev/null; then
    if $check_only; then
        printf 'Read-only check needs git and python3 already installed.\n' >&2; exit 1
    fi
    printf 'Bootstrap needs git, Python and HTTPS certificates from OS packages.\n'
    if ! $assume_yes; then
        read -r -p 'Install bootstrap packages with sudo? [y/N] ' answer </dev/tty
        [[ "$answer" == y || "$answer" == Y ]] || exit 1
    fi
    sudo apt-get update
    sudo apt-get install -y git python3 ca-certificates
fi

script_path="${BASH_SOURCE[0]:-}"
if [[ -n "$script_path" && -f "$script_path" ]]; then
    local_root="$(cd -- "$(dirname -- "$script_path")" && pwd)"
else
    local_root=''
fi
if [[ -n "$local_root" && -f "$local_root/implementation/launcher/install_pi.py" ]]; then
    # A downloaded source checkout can also be installed without fetching again.
    exec python3 "$local_root/implementation/launcher/install_pi.py" "$@"
fi
if $check_only; then
    if [[ ! -f "$install_root/implementation/launcher/install_pi.py" ]]; then
        printf 'No installed source checkout to check; download/clone the repository first.\n' >&2
        exit 1
    fi
    exec python3 "$install_root/implementation/launcher/install_pi.py" "$@"
fi
if [[ -e "$install_root" ]]; then
    [[ -d "$install_root/.git" && -O "$install_root" ]] || { printf 'Existing target is not your Git checkout.\n' >&2; exit 1; }
    existing_remote="$(git -C "$install_root" remote get-url origin)"
    [[ "${existing_remote%.git}" == "${repo_url%.git}" || "${existing_remote%.git}" == "${legacy_repo_url%.git}" ]] || { printf 'Existing checkout uses a different remote.\n' >&2; exit 1; }
    [[ $(git -C "$install_root" branch --show-current) == main ]] || { printf 'Keep existing branches unchanged; install from main.\n' >&2; exit 1; }
    [[ -z $(git -C "$install_root" status --porcelain) ]] || { printf 'Checkout has local changes; preserve them before reinstalling.\n' >&2; exit 1; }
    git -C "$install_root" remote set-url origin "$repo_url"
    git -C "$install_root" fetch origin main
    git -C "$install_root" merge --ff-only FETCH_HEAD
else
    git clone --single-branch --branch main "$repo_url" "$install_root"
fi
printf 'Installing repository revision: '
git -C "$install_root" rev-parse HEAD
exec python3 "$install_root/implementation/launcher/install_pi.py" "$@"
