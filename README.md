# COSMIC OSD — no keyboard layout popup

[Русская инструкция](README.ru.md)

A minimal, unofficial patch that hides **only the keyboard layout popup** in COSMIC. Volume, microphone, brightness indicators, system dialogs, and the polkit agent are left in place. Keyboard shortcuts and keyboard layouts are **not** changed by this project.

This is a version-pinned workaround, not a universal COSMIC extension. It is not affiliated with or endorsed by System76.

## Supported version

| Component | Tested version |
| --- | --- |
| OS / session | Pop!_OS 24.04, COSMIC, Wayland |
| `cosmic-osd` package | `1.10.0~1791315686~24.04~9b14ee0` |
| Upstream commit | `9b14ee017fb8fdb7d03d73da597cf17b89d890f7` |
| Tested architecture | x86_64 |
| Compiler used for validation | Rust 1.95.0 |

The installer **refuses other package versions**. Building successfully on another distribution or architecture does not establish runtime compatibility. No prebuilt binaries are distributed.

## What the patch does

In `src/components/app.rs`, the `KeyboardLayout(Event::Group(...))` handler still records the current group but returns `Task::none()` instead of calling `create_indicator(Params::KeyboardLayout(...))`.

The patch does not disable `cosmic-osd`, remove the Wayland subscription, or modify the keyboard settings. Existing popup-rendering code is intentionally retained to keep the diff small; the compiler therefore reports an expected unused `KeyboardLayout` variant warning.

## Before you start

- Save your work. Restarting OSD briefly interrupts its system dialogs and polkit prompts; do not restart during an authentication prompt.
- Check your package: `dpkg-query -W cosmic-osd`.
- Python 3.11+, Git, a C/C++ toolchain, and Rust **1.95.0** via rustup are required.
- Install rustup from the official Rust installation instructions, then run:

  ```sh
  rustup toolchain install 1.95.0 --profile minimal
  ```

- Typical Debian/Ubuntu native build dependencies are listed below. Review these package operations yourself; this project never runs `sudo` or installs system packages automatically.

  ```sh
  sudo apt-get install build-essential pkg-config cmake clang libclang-dev \
    libinput-dev libudev-dev libxkbcommon-dev libwayland-dev libdbus-1-dev \
    libasound2-dev libfontconfig1-dev libfreetype6-dev libgbm-dev \
    libegl1-mesa-dev libgles2-mesa-dev libssl-dev libpam0g-dev
  ```

A source build downloads dependencies and executes their build scripts. Review the patch and scripts first. Expect several gigabytes of disk use. One build job reduces memory pressure but does **not** impose a hard memory limit. Do not compile on a memory-starved machine without additional resource isolation.

## Build

Clone this repository using GitHub's **Code → Clone** command, open its directory, then:

```sh
bash scripts/build.sh
```

The script fetches the official upstream repository, checks out the exact commit, applies the patch, and runs `cargo check --locked` followed by a development-profile build. Translations are embedded using `rust-embed/debug-embed` so the resulting binary can be moved out of its build directory. This is a functional workaround build, not an optimized release package.

Outputs:

- `build/cosmic-osd` — executable;
- `build/build-info.json` — source revision, architecture, SHA-256;
- `build/source/` — upstream source and build artifacts.

`Cargo.lock` is preserved. Existing `build/` directories are not overwritten. Network access is needed, and current toolchain availability or upstream dependency availability may affect future builds.

## Install for your user only

**Do not use sudo.** Review the scripts first.

```sh
python3 scripts/manage.py install
```

The installer checks the package version, architecture, and build checksum, then installs to `~/.local/bin/cosmic-osd`. It refuses to overwrite an existing override. The package-managed `/usr/bin/cosmic-osd` is not modified and remains the rollback copy. Checksums detect accidental changes; they are not a signature or proof of trust.

Installation does not restart anything. To activate, either log out and back in, or restart **only OSD**:

```sh
python3 scripts/manage.py restart
python3 scripts/manage.py status
```

The restart command requires exactly one OSD process owned by you and managed by `cosmic-session`. It verifies that the session's `PATH` resolves `cosmic-osd` to the user override, then sends SIGTERM to that process through a pidfd. COSMIC's session manager is expected to respawn it. No desktop/session restart is requested.

If your session's `PATH` does not put `~/.local/bin` before `/usr/bin`, restart is refused. A new login alone will not fix an incorrectly ordered PATH: configure your login environment first. This repository does not alter shell startup files.

## Verify

```sh
python3 scripts/manage.py status
```

The running executable should be `~/.local/bin/cosmic-osd`. Switch layouts: the language popup should no longer appear. Check volume/brightness indicators and authentication dialogs normally; the project does not automate UI or authentication interactions.

Validation performed on the pinned source: compilation/type checking, full development build, local `--help` execution, patch applicability, and startup with responsive D-Bus interfaces. These checks do not constitute a complete graphical or polkit regression test. Upstream currently has no unit tests in this binary target. This repository includes isolated installer tests:

```sh
python3 -m unittest discover -s tests -v
bash -n scripts/build.sh
```

## Rollback

From this checkout:

```sh
python3 scripts/manage.py uninstall
```

Then **log out and back in**. Uninstall refuses to remove a locally modified override or to proceed when the system original is unavailable. It does not stop any process.

Manual recovery, including if this checkout is lost: move `~/.local/bin/cosmic-osd` outside your PATH, verify that `/usr/bin/cosmic-osd` is present, then log out and back in. Do not delete or overwrite the system original. If reinstalling later, first inspect/remove the stale `~/.local/share/cosmic-osd-no-layout-popup/install.json` record after confirming the old override is gone.

## Important: COSMIC updates

**The user override takes precedence over future package updates.** Uninstall it before upgrading COSMIC. Do not keep an old OSD indefinitely: it also handles security-sensitive authentication dialogs. After an update, use the distribution's OSD until this patch has been reviewed, rebuilt, and tested against the new version. The installed override does not automatically disable itself when packages change.

The installer intentionally refuses pre-existing overrides, including an earlier manually installed copy of this workaround. Do not force overwrite them; preserve the existing file and review its provenance first.

## License and attribution

GPL-3.0-or-later, matching upstream's package declaration. See [LICENSE](LICENSE). The license document's own title is GPL version 3; the project's grant permits version 3 or later.

Upstream: [pop-os/cosmic-osd](https://github.com/pop-os/cosmic-osd), developed by System76 and contributors. This repository distributes a small modification, not the full upstream source or its branding assets. Preserve upstream notices when redistributing patched source. This repository's patch, scripts, and documentation are provided under GPL-3.0-or-later, without warranty. No telemetry, credentials, or personal keyboard configuration are included.
