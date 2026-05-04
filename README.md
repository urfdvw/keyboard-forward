# keyboard-forward

Forward your computer's keyboard to a Bluetooth device using a BLE microcontroller as a HID bridge.

## How It Works

1. The BLE microcontroller connects to your computer over USB and exposes a Web Serial data port.
2. `index.html` connects to that serial port and either:
  - captures your keyboard globally while capture mode is enabled, or
  - sends text from the textarea as a stream of HID key presses.
3. The CircuitPython firmware receives binary key commands over `usb_cdc.data`.
4. The Microcontroller replays those commands as a BLE keyboard to the paired target device.

## Requirements

### Hardware

- BLE microcontroller
  - tested with Seeed Xiao nrf52840 
- USB-C cable

### Software

- CircuitPython 10
- CircuitPython libraries on the device:
  - `adafruit_ble`
  - `adafruit_hid`
- A Chromium-based browser such as Chrome, Edge, or Brave

## Setup

### 1. Flash the firmware

Copy both files from `firmware/` to the root of the `CIRCUITPY` drive:

```text
CIRCUITPY/
├── boot.py
└── code.py
```

After copying, the board reboots. Your computer should show two USB serial ports:

- the console / REPL port
- the data port used by the web app

### 2. Open the web app

Open https://urfdvw.github.io/keyboard-forward/ in Chrome or Edge.

Or open index.html as a web page file in in Chrome or Edge.

### 3. Connect serial

Click `Connect Serial` and choose the CircuitPython's data serial port. The status badge should show `Idle`.

### 4. Pair BLE

1. Put the target device in Bluetooth scan / pairing mode.
2. Click `Pair BLE`.
3. Pair with `ForwardHID` on the target device.
4. Wait for the web app status to change to `Connected: <device name>`.

## Usage

### Live Keyboard Capture

1. Click `Start Capture`.
2. Type normally on your computer keyboard.
3. Keystrokes are forwarded to the paired BLE target until you click `Stop Capture`.

While capture is on:

- the page installs global `keydown` and `keyup` listeners
- browser defaults are prevented for captured keys
- modifier state is tracked and sent as a full modifier bitmask
- typing inside the send-text textarea is ignored so you can still edit it locally

Stopping capture sends `KEY_RELEASE_ALL` so held keys are released on the target device.

### Send Text

Paste or type ASCII text into the textarea and click `Send`.

- text is sent one character at a time using a US QWERTY ASCII map
- unsupported characters are skipped
- `\n` is sent as Enter
- live capture is automatically stopped before text send begins

## Notes

- The current firmware is keyboard-only. Mouse move, click, and scroll are not forwarded in this revision.
- The key mapping assumes a US QWERTY keyboard layout on the target device.
- Some browser or OS shortcuts may still be intercepted before the page sees them.
- The firmware prints debug logs such as `KEY_DOWN`, `KEY_UP`, and `entered CONN state` to the console serial port.

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Keyboard does not type on target | Confirm BLE status is `Connected`, then stop and restart capture |
| `Connect Serial` does nothing | Use Chrome or Edge and serve over `http://localhost` |
| Only one serial port appears | Make sure `boot.py` is present in the `CIRCUITPY` root |
| Pairing seems stale | Forget `ForwardHID` on the target device and pair again |
| Typed characters are wrong | Set the target device keyboard layout to US English |
| Want mouse forwarding | It is not part of the current firmware path and would need to be reintroduced in both `index.html` and `firmware/code.py` |

## Project Structure

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
