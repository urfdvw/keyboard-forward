# CLAUDE.md — keyboard-forward Technical Reference

## What This Project Does

Current repo state: BLE keyboard forwarder.

- The Xiao nrf52840 receives keyboard commands over USB serial.
- It replays them as a BLE keyboard to the paired target device.
- The host UI is a single `index.html` file using Web Serial.
- The current firmware does not implement mouse forwarding.

## File Map

| File | Role |
|------|------|
| `firmware/boot.py` | enables `usb_cdc` console and data ports |
| `firmware/code.py` | BLE keyboard bridge and serial command loop |
| `index.html` | serial host UI for live capture and send-text |
| `README.md` | user-facing setup and usage |
| `design.md` | full design / protocol spec |

## Serial Protocol Quick Reference

### Host → Device

```text
0x01              ADVERTISE         (1 byte total)
0x03 M K          KEY_DOWN          (3 bytes: modifier, keycode)
0x04 M K          KEY_UP            (3 bytes: modifier, keycode)
0x05              KEY_RELEASE_ALL   (1 byte)
```

```python
CMD_SIZES = {0x01: 0, 0x03: 2, 0x04: 2, 0x05: 0}
```

### Device → Host

```text
IDLE\n
ADV\n
CONN:<name>\n
DISC\n
```

## BLE HID Notes

- `HIDService()` uses Adafruit's built-in HID descriptor.
- `Keyboard(hid.devices)` finds the keyboard device automatically.
- The firmware currently sends only keyboard reports.
- `_apply_mod()` keeps modifier key state synchronized from the host's modifier bitmask.

Modifier bit layout:

```text
bit0=L-Ctrl  bit1=L-Shift  bit2=L-Alt  bit3=L-GUI
bit4=R-Ctrl  bit5=R-Shift  bit6=R-Alt  bit7=R-GUI
```

Modifier bit `i` maps to HID keycode `0xE0 + i`.

## Key Pieces in `firmware/code.py`

- `poll_serial(serial, dispatch)` handles fragmented reads and fixed-length packets.
- `_apply_mod(new_mod)` diffs the previous and current modifier bitmasks and presses or releases modifier keys.
- `cmd_key_down(payload)` applies modifiers first, then presses the non-modifier key if present.
- `cmd_key_up(payload)` releases the non-modifier key first, then applies the new modifier mask.
- `cmd_release_all()` calls `keyboard.release_all()` and clears `_current_mod`.
- `poll_ble()` transitions `IDLE -> ADV -> WAIT -> CONN` and resets state on disconnect.

## Host UI Notes

The current `index.html` supports two keyboard paths:

1. Live capture
   - global document-level `keydown` / `keyup`
   - enabled by `Start Capture`
   - disabled by `Stop Capture`, disconnect, or before send-text begins
2. Send text
   - textarea-driven
   - ASCII-only using a US QWERTY `ASCII_MAP`
   - sends down/up pairs with small delays for reliability

## Debug Output

The firmware prints debug messages to the console serial port, including:

- `KEY_DOWN state=... mod=.. kc=..`
- `KEY_UP state=... mod=.. kc=..`
- `press ok`
- `entered CONN state`
- `KBD ERR ...`
- `MOD ERR ...`

These are not sent over the data serial port used by the web app.

## Known Caveats

- Mouse forwarding is currently out of scope for this branch.
- Web Serial requires Chrome / Edge / another Chromium browser.
- The UI and ASCII map assume US QWERTY layout.
- Some browser / OS shortcuts may bypass the page.
- Remote name lookup may return `Unknown` because it uses a private BLE connection field.
