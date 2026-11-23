# CERF E-55 serial over a Windows named pipe (86Box -> ActiveSync)

Status: proof of concept. **The code compiles (MinGW syntax check) but has NOT been run, and the CI workflow has not yet been verified.**
No Windows, 86Box, Wine or E-55 ROM was available where this was written.

## Findings

- The E-55 is board family `casio_tomcat` (`libCerfCore/db/boards/casio_cassiopeia_e55.json`, `bootable_full`).
  Its COM1 is a VR41xx SIU wired by `src/boards/casio_tomcat/casio_tomcat_serial_wiring.cpp`
  (DCD on a GIU pin, supply on GPIO 38).
- CERF already bridges a guest COM port to a host COM port: `HostSerialForward`
  (`src/peripherals/serial/host_serial_forward.cpp`) over `HostSerialPort` (`src/platform/host_serial_port_*.cpp`),
  with baud/format, DTR/RTS out, CTS/DSR/RI/DCD in, break, and baud-paced TX.
  So a named pipe only needs a new `HostSerialPort` backend. No board code changes.
- It is not a standalone "E-55 only" codebase: boards are registered via `REGISTER_SERVICE` in the
  separate `libCerfCore` repo (a submodule of `cerf`), built with vcpkg + Qt. I did **not** physically strip other
  devices: that is a large unbuilt/untestable refactor and the pipe backend is board-independent. At run time the
  E-55 is selected with `--device=<name>`; a ROM image is not shipped and must be provided by you.

## Repository layout / GitHub build

- `patches/libCerfCore-named-pipe.patch` - the backend + menu entries, against libCerfCore `379f8b1` (the commit upstream pins).
- `tools/trim_e55.py` - trims the board database to the E-55 only (and skips the CE guest apps, which need a private toolchain).
- `.github/workflows/build-e55.yml` - checks out `gweslab/cerf` at the commit in `UPSTREAM.txt`, applies the patch, trims, and builds
  Windows x86 with upstream's own `build.py`. Artifact: `cerf-e55-named-pipes-win32`. Run it from the Actions tab (or push to `main`).
  The first run builds Qt/vcpkg from source (1h+); later runs use caches.
- "E-55 only" means the device list, the board database and the board family. The C++ of other boards is still compiled but dead
  (it only registers for its own board family). Physically deleting it needs a local build to check; not done.

## GUI

Right-click (or click) the COM socket icon in the emulator's socket bar > Insert > Serial Port Forwarder. New entries:
- `Named pipe \\.\pipe\cerf_com1 (connect - 86Box server)`
- `Named pipe \\.\pipe\cerf_com1 (listen - 86Box client)`
plus any pipes from `CERF_SERIAL_PIPES`. The pipe name is fixed at `cerf_com1` in the menu (a free-text prompt is not implemented);
use that name in 86Box or set `CERF_SERIAL_PIPES` for others.

## What the patch does (Windows only)

- `HostSerialPort::Open` accepts:
  - `pipe:NAME` or `\\.\pipe\NAME`: CERF connects as a client to a pipe someone else created (86Box **Server**).
  - `pipe-server:NAME`: CERF creates `\\.\pipe\NAME` and waits (86Box **Client**).
- Pipe mode skips DCB/comm timeouts. Byte stream, overlapped I/O, same threading as COM mode.
- Modem lines are synthesized: CTS+DSR+DCD asserted while a peer is connected, all low when not.
  DTR/RTS/break from the guest are accepted and dropped (a pipe cannot carry them).
- Both modes survive the peer going away: server mode re-listens, client mode retries every 250 ms. Bytes written with no peer are dropped,
  and the synthesized CTS/DSR/DCD drop while disconnected.
- Pipes are offered in the serial-forward "insert" menu: two fixed entries for `cerf_com1`, plus any from the env var
  `CERF_SERIAL_PIPES="pipe:other;pipe-server:another"` (set before launching CERF).

## 86Box + ActiveSync setup

1. 86Box: Win98 machine, Settings > Ports (COM & LPT) > enable COM1, device **Serial Passthrough**.
   Configure it: mode **Named Pipe (Server)**, pipe name e.g. `cerf_com1` (86Box makes `\\.\pipe\cerf_com1`).
   (Option B: 86Box **Named Pipe (Client)** and use `pipe-server:cerf_com1` in CERF.) Set 86Box's host
   baud/"data bits" to match if it asks; start the VM first for option A.
2. CERF: run the E-55 (you supply the ROM), open the COM socket menu > Insert > Serial Port Forwarder >
   "Named pipe ... (connect - 86Box server)".
3. Win98: install ActiveSync 3.x, Settings > Connection Settings: allow serial cable connection on COM1.
   Set the guest COM1 to 115200 (ActiveSync's default) or lower (19200/57600) if unreliable.
4. On the E-55, start the connection (Start > Programs > Communication > ActiveSync / or cradle with a serial cable).

## VirtualBox

Machine Settings > Serial Ports > Port 1: Enable, COM1, **Port Mode = Host Pipe**, Path/Address `\\.\pipe\cerf_com1`.
- **"Create Pipe" checked** (VirtualBox is the server): in CERF use the **connect** entry. This is the usual choice.
- **"Create Pipe" unchecked** (VirtualBox is the client): it needs the pipe to already exist, so insert the CERF **listen** entry first, then start the VM.
With "connect", the "Create Pipe" checkbox *must* be on, otherwise nobody creates the pipe and CERF has nothing to connect to.
Newer builds keep retrying the connection every 250 ms and reconnect on their own when the VM reboots, so start order no longer matters
for "connect", and you no longer need to eject/re-insert after a guest reboot.

## Risks / unknowns (please test)

- Untested at runtime. Pipe semantic details (86Box message vs byte mode, flow on a full pipe) are unverified.
- 86Box passthrough does not model baud or DTR/DSR; the guest ActiveSync sees an always-ready port. The CE side sees
  the synthesized CTS/DSR/DCD only. If ActiveSync wants DTR toggling to wake the link, this may need an
  in-band workaround (e.g. forcing DCD pulses on connect).
- CERF paces guest->host bytes at the guest baud; host->guest bytes are pushed as fast as they arrive, which
  could overrun the guest UART FIFO at 115200 (check `PushRx`/flow control if you see dropped bytes).
- CE ActiveSync over serial uses PPP-ish/"Direct connection" framing and an `CLIENT`/`CLIENTSERVER` handshake;
  a wrong baud on either side will hang silently.
- License: CERF is noncommercial with attribution ("Based on CE Runtime Foundation - https://cerf.cx"). Keep that if you distribute.
- Linux/macOS backends were not changed.
