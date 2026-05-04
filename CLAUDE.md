# CLAUDE.md — keyboard-forward Technical Reference

## What This Project Does

BLE HID forwarder: Xiao nrf52840 (CircuitPython 10.2) receives mouse/keyboard commands over USB serial and replays them as BLE HID events (absolute mouse + keyboard) to a paired target device. Host UI is a single HTML file using Web Serial API.

## File Map

| File | Role |
|------|------|
| `firmware/boot.py` | `usb_cdc.enable(console=True, data=True)` — must run before code.py |
| `firmware/code.py` | BLE HID + serial command loop |
| `index.html` | Web Serial host app — mirror area + keyboard capture |
| `design.md` | Full spec: protocol tables, HID descriptor, state machine |

Firmware files are copied to the **root of the CIRCUITPY drive** on the device.

## Serial Protocol Quick Reference

### Host → Device (binary, fixed-length)

```
0x01              ADVERTISE         (1 byte total)
0x02 B X0 X1 Y0 Y1 W  MOUSE_MOVE  (7 bytes: buttons, x LE, y LE, wheel signed)
0x03 M K          KEY_DOWN         (3 bytes: modifier, keycode)
0x04 M K          KEY_UP           (3 bytes: modifier, keycode)
0x05              KEY_RELEASE_ALL  (1 byte)
0x06 B            MOUSE_BUTTONS    (2 bytes: buttons)
```

CMD_SIZES = `{0x01:0, 0x02:6, 0x03:2, 0x04:2, 0x05:0, 0x06:1}`

### Device → Host (ASCII lines)

```
IDLE\n   ADV\n   CONN:<name>\n   DISC\n
```

## BLE HID Reports

- Report ID 1 = Keyboard: `[modifier, 0x00, key0, key1, key2, key3, key4, key5]`
- Report ID 2 = Absolute Mouse: `struct.pack("<BHHb", buttons, x, y, wheel)` (6 bytes)
- X/Y range: 0–32767
- `hid.devices[0]` = keyboard, `hid.devices[1]` = mouse (verify on first run)

## Key Classes in `code.py`

- `KbdState(dev)` — manages 8-byte keyboard report; `key_down(mod, kc)`, `key_up(mod, kc)`, `release_all()`
- `MouseState(dev)` — manages mouse report; `move(buttons, x, y, wheel)`, `set_buttons(buttons)`
- `poll_serial(serial)` — stateful fragmented-read parser, dispatches to command handlers
- `poll_ble()` — checks BLE connection state, sends CONN/DISC status lines

## BLE State Machine

`IDLE` → (ADVERTISE cmd) → `ADV` → (ble.connected) → `CONN` → (!ble.connected) → `IDLE`

Commands are only forwarded in `CONN` state. `release_all()` is called on disconnect.

## Known Caveats

- Web Serial requires Chromium-based browser (Chrome/Edge). Firefox and Safari do not support it.
- Web Serial requires a secure context: serve `index.html` via `python3 -m http.server` (localhost).
- Remote device name retrieval (`ble._connections[0]._connection._remote_name`) uses a private API and may break on adafruit_ble updates; defaults to "Unknown" on AttributeError.
- Browser will intercept some key combos (Cmd+W, Cmd+Q, etc.) even with `preventDefault()`.
- The `absolute_mouse` (neradoc) library is USB HID only — not used. BLE absolute mouse is implemented via custom HID descriptor.
- `hid.devices` ordering depends on descriptor order; confirm Report ID → device index mapping on first hardware run.

## HID Descriptor Summary

142 bytes total. Keyboard (Report ID 1, 8-byte report) followed by Absolute Mouse (Report ID 2, 6-byte report). Full bytes in `design.md` § BLE HID and in `firmware/code.py`.

## Modifier Byte Bitmask

```
bit0=L-Ctrl  bit1=L-Shift  bit2=L-Alt  bit3=L-GUI
bit4=R-Ctrl  bit5=R-Shift  bit6=R-Alt  bit7=R-GUI
```

## Button Byte Bitmask

`bit0 = left`, `bit1 = right`, `bit2 = middle`
