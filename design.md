# keyboard-forward — Design Specification

## Overview

The current implementation is a BLE keyboard bridge built around a Xiao nrf52840 running CircuitPython 10.2.

- The browser app connects to the Xiao over Web Serial.
- The browser can either capture live keyboard events or send ASCII text from a textarea.
- The firmware converts those serial commands into BLE keyboard reports for a paired target device.

Mouse forwarding is not implemented in the current firmware revision.

```text
Host computer
  ├── Browser (index.html)
  │     ├── Global keyboard capture
  │     ├── ASCII text sender
  │     └── Web Serial → USB CDC data port
  └── USB cable
         ↕ binary serial protocol
Xiao nrf52840 (CircuitPython)
  ├── usb_cdc.data  ← receives commands
  ├── BLERadio + HIDService → BLE advertising / pairing
  └── BLE HID keyboard reports
         ↕ Bluetooth
Target device (Android / iPad / PC / etc.)
```

## Hardware / Runtime

- MCU: Seeed Xiao nrf52840
- Firmware runtime: CircuitPython 10.2
- Browser requirement: Chromium-based browser with Web Serial support

Libraries used on the device:

- `adafruit_ble`
- `adafruit_hid`
- `usb_cdc`

## Firmware Architecture

The firmware uses:

- `HIDService()` with Adafruit's built-in HID descriptor
- `Keyboard(hid.devices)` from `adafruit_hid.keyboard`
- a compact binary serial protocol over `usb_cdc.data`
- a small BLE connection state machine with an extra `WAIT` phase before entering `CONN`

Important implementation detail:

- the firmware does not manually build an 8-byte keyboard report anymore
- instead, it drives `Keyboard.press()`, `Keyboard.release()`, and `Keyboard.release_all()`
- modifier bits are synchronized separately by `_apply_mod()`

## Serial Protocol

### Transport

- Port: `usb_cdc.data`
- Baud rate used by host: `115200`
- Host to device: fixed-length binary packets
- Device to host: newline-delimited ASCII status messages

### Host → Device Commands

Each packet starts with a 1-byte command code.

| Code | Name | Total bytes | Payload |
|------|------|-------------|---------|
| `0x01` | `ADVERTISE` | 1 | none |
| `0x03` | `KEY_DOWN` | 3 | `modifier(1) keycode(1)` |
| `0x04` | `KEY_UP` | 3 | `modifier(1) keycode(1)` |
| `0x05` | `KEY_RELEASE_ALL` | 1 | none |

Current firmware command table:

```python
CMD_SIZES = {0x01: 0, 0x03: 2, 0x04: 2, 0x05: 0}
```

### Modifier Byte Layout

The browser sends the full current modifier bitmask.

```text
bit0 = Left Ctrl
bit1 = Left Shift
bit2 = Left Alt
bit3 = Left GUI
bit4 = Right Ctrl
bit5 = Right Shift
bit6 = Right Alt
bit7 = Right GUI
```

The firmware maps bit `i` to HID keycode `0xE0 + i`.

### Device → Host Status Lines

| Line | Meaning |
|------|---------|
| `IDLE\n` | initial state after boot |
| `ADV\n` | BLE advertising has started |
| `CONN:<name>\n` | BLE connected; remote name if available |
| `DISC\n` | BLE disconnected |

### Debug Logging

The firmware also prints debug output to the console / REPL serial port, including:

- `KEY_DOWN state=... mod=.. kc=..`
- `KEY_UP state=... mod=.. kc=..`
- `press ok`
- `entered CONN state`
- `KBD ERR ...`
- `MOD ERR ...`

## BLE State Machine

```text
IDLE ──[ADVERTISE]──► ADV ──[ble.connected]──► WAIT ──[2s delay]──► CONN
   ▲                                                           │
   └──────────────────────────────[disconnect]─────────────────┘
```

Behavior by state:

- `IDLE`: not advertising, not forwarding input
- `ADV`: advertising and waiting for pairing / connection
- `WAIT`: BLE connected, but firmware delays 2 seconds before sending HID input
- `CONN`: keyboard commands are forwarded

On disconnect:

- the state returns to `IDLE`
- `_current_mod` is reset to `0`
- `keyboard.release_all()` is called
- `DISC` is sent to the host

## Host Application (`index.html`)

### UI

The current UI has three functional areas:

1. Connection
   - `Connect Serial`
   - `Pair BLE`
   - connection status badge
2. Keyboard
   - `Start Capture` / `Stop Capture`
3. Send Text
   - textarea for ASCII text
   - `Send` button

The main panel shows animated indicators for:

- live keyboard capture
- text send in progress

### Keyboard Capture Flow

The browser listens at `document` level, not inside a mirror div.

Capture rules:

- capture only runs when `capturing === true`
- `keydown` / `keyup` call `preventDefault()`
- events originating from `TEXTAREA` or `INPUT` elements are ignored
- modifier state is tracked in `currentMod`

Key handling order:

1. If `e.code` is in `MOD_MAP`, update `currentMod` and send modifier-only packet.
2. Otherwise, if `e.code` is in `KEY_MAP`, send the HID keycode with the current modifier byte.

Stopping capture calls:

```javascript
sendReleaseAll();
```

### Send Text Flow

The browser supports a US QWERTY ASCII map:

- lowercase and uppercase letters
- digits
- whitespace
- common punctuation
- shifted punctuation

Send behavior:

1. Stop live capture if it is active.
2. Iterate through each character in the textarea.
3. Skip bare `\r`.
4. Skip unsupported characters.
5. Send key down.
6. Wait 30 ms.
7. Send key up with `modifier = 0x00`.
8. Wait 20 ms.

This path is intentionally simple and favors reliability over throughput.

### Key Maps

The browser contains:

- `MOD_MAP`: `event.code` → modifier bitmask
- `KEY_MAP`: `event.code` → USB HID keycode
- `ASCII_MAP`: printable ASCII character → `[keycode, modifier]`

These mappings assume a US QWERTY layout on the target device.

## Known Limitations

- Mouse forwarding is not implemented in the current firmware.
- Some browser or OS shortcuts may never reach the page.
- `ASCII_MAP` is ASCII-only and skips unsupported characters.
- Remote device name lookup uses a private `adafruit_ble` connection field and may return `Unknown`.

## File Structure

```text
keyboard-forward/
├── README.md
├── CLAUDE.md
├── design.md
├── index.html
└── firmware/
    ├── boot.py
    └── code.py
```
