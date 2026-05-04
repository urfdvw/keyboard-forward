# keyboard-forward — Design Specification

## Overview

The Xiao nrf52840 (CircuitPython 10.2) acts as a BLE HID device (keyboard + absolute mouse). A host computer runs `index.html` (single-file web app), which captures mouse and keyboard input in a "mirror area" and sends commands to the microcontroller over USB serial (Web Serial API). The firmware decodes these commands and replays them as BLE HID events to a paired target device.

```
Host computer
  ├── Browser (index.html)
  │     ├── Mouse mirror area → captures pointermove / click / scroll
  │     ├── Keyboard capture → captures keydown / keyup
  │     └── Web Serial → USB CDC data port
  └── USB cable
         ↕ binary serial protocol
Xiao nrf52840 (CircuitPython)
  ├── usb_cdc.data  ← receives commands
  ├── BLERadio + HIDService → BLE HID advertise / pair
  └── BLE HID events → keyboard + absolute mouse
         ↕ Bluetooth
Target device (iPad, phone, PC, …)
```

---

## Hardware

- **MCU**: Seeed Xiao nrf52840
- **Firmware**: CircuitPython 10.2
- **Libraries used**:
  - `adafruit_ble` — BLE stack
  - `adafruit_hid` — HID report helpers (Keyboard class)
  - `usb_cdc` — USB CDC serial
  - `struct` — binary packing

> The `circuitpython_absolute_mouse` library (neradoc) is USB HID only and is **not** used for BLE. A custom HID report descriptor handles absolute mouse over BLE.

---

## Serial Protocol

### Transport

- Port: `usb_cdc.data` (second USB CDC device, enabled in `boot.py`)
- Baud: 115200
- Format: binary (host → device), ASCII lines (device → host)

### Host → Device (fixed-length binary packets)

Each packet starts with a 1-byte command code. Payload length is fixed per command; no framing delimiters.

| Code | Name | Total bytes | Payload layout |
|------|------|-------------|----------------|
| `0x01` | ADVERTISE | 1 | — |
| `0x02` | MOUSE_MOVE | 7 | `buttons(1) x_lo x_hi y_lo y_hi wheel_s8` |
| `0x03` | KEY_DOWN | 3 | `modifier(1) keycode(1)` |
| `0x04` | KEY_UP | 3 | `modifier(1) keycode(1)` |
| `0x05` | KEY_RELEASE_ALL | 1 | — |
| `0x06` | MOUSE_BUTTONS | 2 | `buttons(1)` |

Field definitions:

- **`x`, `y`**: uint16 little-endian, range 0–32767 (HID absolute coordinates)
- **`wheel_s8`**: signed int8 encoded as uint8 on wire. Negative values: `byte = delta + 256`. Range: −127 to +127.
- **`buttons`**: bitmask — `bit0 = left`, `bit1 = right`, `bit2 = middle`
- **`modifier`**: bitmask — `bit0 = L-Ctrl`, `bit1 = L-Shift`, `bit2 = L-Alt`, `bit3 = L-GUI`, `bit4 = R-Ctrl`, `bit5 = R-Shift`, `bit6 = R-Alt`, `bit7 = R-GUI`
- **`keycode`**: USB HID keycode (0x00 = none / modifier-only)

MOUSE_BUTTONS (0x06) is for click events without position update. Scroll is baked into MOUSE_MOVE's `wheel_s8` byte; for pure scroll events the host re-sends the last known coordinates with the wheel delta.

Firmware payload size table: `CMD_SIZES = {0x01:0, 0x02:6, 0x03:2, 0x04:2, 0x05:0, 0x06:1}`

### Device → Host (ASCII newline-terminated lines)

| Line | Meaning |
|------|---------|
| `IDLE\n` | Boot state; also sent after BLE disconnect |
| `ADV\n` | Advertising, waiting for BLE pairing |
| `CONN:<name>\n` | Connected; `<name>` = remote device name (UTF-8) |
| `DISC\n` | BLE connection dropped |

---

## BLE HID

### Custom HID Report Descriptor

Two reports share one descriptor. The keyboard layout mirrors `adafruit_hid.keyboard.Keyboard` so its `press()`/`release()` methods work over BLE.

| Report ID | Type | Payload |
|-----------|------|---------|
| 1 | Keyboard | 8 bytes: modifier(1) + reserved(1) + keycodes[6] |
| 2 | Absolute Mouse | 6 bytes: buttons(1) + X uint16LE + Y uint16LE + wheel int8 |

Mouse report packed as: `struct.pack("<BHHb", buttons, x, y, wheel)`

X and Y range: 0–32767 (logical maximum declared in descriptor).

### BLE State Machine

```
IDLE ──[0x01 ADVERTISE]──► ADV ──[ble.connected]──► CONN
                                                       │
                                         [!ble.connected]
                                                       ▼
                                                     IDLE
```

- Only MOUSE_MOVE, MOUSE_BUTTONS, KEY_DOWN, KEY_UP, KEY_RELEASE_ALL are forwarded when state is CONN.
- On disconnect, firmware calls `kbd.release_all()` before transitioning to IDLE.

---

## Host Application (`index.html`)

### Requirements

- Single file, no external dependencies
- Chromium-based browser required (Web Serial API not available in Firefox/Safari)
- Must be served from a secure context: `localhost` via `python3 -m http.server` or similar

### UI Layout

```
┌──────────────────────┬────────────────────────────────┐
│ Settings (240px)     │  Mouse mirror area              │
│                      │  (width = user setting,         │
│ [Connect Serial]     │   height = width × resH/resW)   │
│ [Pair BLE]           │                                 │
│ Status: ● Connected  │  div#mirror                     │
│         to "iPad"    │  tabindex=0                     │
│                      │  cursor: crosshair              │
│ Resolution:          │                                 │
│ [2360] × [1640]      │                                 │
│                      │                                 │
│ Mirror width:        │                                 │
│ [600] px             │                                 │
└──────────────────────┴────────────────────────────────┘
```

### Mouse Mirror Logic

```
mirrorHeight = mirrorWidth × resH / resW

On pointermove:
  relX = event.clientX − mirrorRect.left
  relY = event.clientY − mirrorRect.top
  hidX = clamp(round(relX / mirrorWidth  × 32767), 0, 32767)
  hidY = clamp(round(relY / mirrorHeight × 32767), 0, 32767)
  → send MOUSE_MOVE(hidX, hidY, mouseButtons, 0)
```

The logical resolution setting determines the mirror's aspect ratio; it does not affect coordinate scaling (coordinates always map 0–32767 to the full mirror area).

### Keyboard Capture

The mirror div has `tabindex=0`. On `mouseenter` it receives focus. `keydown`/`keyup` events are captured and `preventDefault()` is called on all to suppress browser shortcuts.

Key lookup order:
1. Check `MOD_MAP[e.code]` → update modifier bitmask
2. Check `KEY_MAP[e.code]` → get HID keycode

On `mouseleave`: send KEY_RELEASE_ALL, reset modifier and button state.

### HID Keycode Map

```javascript
// Modifier map: event.code → modifier bitmask
const MOD_MAP = {
  ControlLeft:0x01, ShiftLeft:0x02, AltLeft:0x04, MetaLeft:0x08,
  ControlRight:0x10, ShiftRight:0x20, AltRight:0x40, MetaRight:0x80
};

// Key map: event.code → USB HID keycode
const KEY_MAP = {
  // Letters (0x04-0x1D)
  KeyA:0x04 … KeyZ:0x1D,
  // Digits (Digit0=0x27, Digit1=0x1E … Digit9=0x26)
  Digit1:0x1E … Digit0:0x27,
  // Common keys
  Enter:0x28, Escape:0x29, Backspace:0x2A, Tab:0x2B, Space:0x2C,
  Minus:0x2D, Equal:0x2E, BracketLeft:0x2F, BracketRight:0x30,
  Backslash:0x31, Semicolon:0x33, Quote:0x34, Backquote:0x35,
  Comma:0x36, Period:0x37, Slash:0x38, CapsLock:0x39,
  F1:0x3A … F12:0x45,
  Insert:0x49, Home:0x4A, PageUp:0x4B, Delete:0x4C,
  End:0x4D, PageDown:0x4E,
  ArrowRight:0x4F, ArrowLeft:0x50, ArrowDown:0x51, ArrowUp:0x52,
};
```

---

## File Structure

```
keyboard-forward/
├── design.md          ← this file
├── CLAUDE.md          ← technical quick-reference for AI/dev
├── README.md          ← user guide
├── index.html         ← host web app (single file)
└── firmware/
    ├── boot.py        ← enable usb_cdc data port
    └── code.py        ← main firmware loop
```

Firmware files must be copied to the root of the CIRCUITPY drive on the device. They are stored under `firmware/` in this repo for version control only.
