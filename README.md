# CERF E-55 serial over a Windows named pipe (86Box -> ActiveSync)

Status: proof of concept. **The code compiles (MinGW syntax check) but has NOT been run.**
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

## What the patch does (`0001-...patch`, against libCerfCore, Windows only)

- `HostSerialPort::Open` accepts:
  - `pipe:NAME` or `\\.\pipe\NAME`: CERF connects as a client to a pipe someone else created (86Box **Server**).
  - `pipe-server:NAME`: CERF creates `\\.\pipe\NAME` and waits (86Box **Client**).
- Pipe mode skips DCB/comm timeouts. Byte stream, overlapped I/O, same threading as COM mode.
- Modem lines are synthesized: CTS+DSR+DCD asserted while a peer is connected, all low when not.
  DTR/RTS/break from the guest are accepted and dropped (a pipe cannot carry them).
- Server mode survives the peer disconnecting and waits for a new one; bytes written with no peer are dropped.
  Client mode reports the bridge dead if the pipe breaks (re-insert the port).
- Pipes are offered in the serial-forward "insert" menu through the env var
  `CERF_SERIAL_PIPES="pipe:cerf_com1;pipe-server:cerf_com2"` (set before launching CERF).

## 86Box + ActiveSync setup

1. 86Box: Win98 machine, Settings > Ports (COM & LPT) > enable COM1, device **Serial Passthrough**.
   Configure it: mode **Named Pipe (Server)**, pipe name e.g. `cerf_com1` (86Box makes `\\.\pipe\cerf_com1`).
   (Option B: 86Box **Named Pipe (Client)** and use `pipe-server:cerf_com1` in CERF.) Set 86Box's host
   baud/"data bits" to match if it asks; start the VM first for option A.
2. CERF: `set CERF_SERIAL_PIPES=pipe:cerf_com1`, run with `--device=` for the E-55, then insert the serial
   forward from the COM socket menu and pick `pipe:cerf_com1`.
3. Win98: install ActiveSync 3.x, Settings > Connection Settings: allow serial cable connection on COM1.
   Set the guest COM1 to 115200 (ActiveSync's default) or lower (19200/57600) if unreliable.
4. On the E-55, start the connection (Start > Programs > Communication > ActiveSync / or cradle with a serial cable).

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
