# keyboard-forward

Forward your computer's mouse and keyboard to any Bluetooth device using a Seeed Xiao nrf52840 as a BLE HID bridge.

## How It Works

1. The Xiao nrf52840 connects to your computer via USB and appears as a BLE keyboard + absolute mouse to a target device (iPad, Android phone, another PC, etc.).
2. A web app (`index.html`) captures your mouse movements, clicks, scroll, and keystrokes inside a "mirror area" and sends them to the microcontroller over USB serial.
3. The microcontroller replays those inputs on the target device via Bluetooth.

## Requirements

### Hardware
- Seeed Xiao nrf52840
- USB-C cable

### Software
- CircuitPython 10.2 installed on the Xiao ([install guide](https://learn.adafruit.com/getting-started-with-the-nrf52840-xiao-with-circuitpython))
- Required CircuitPython libraries on the device:
  - `adafruit_ble`
  - `adafruit_hid`
- A Chromium-based browser (Chrome, Edge, Brave) — Web Serial API is not available in Firefox or Safari

## Setup

### 1. Flash the firmware

Copy both files from the `firmware/` folder to the **root** of the `CIRCUITPY` drive:

```
CIRCUITPY/
├── boot.py
└── code.py
```

After copying, the Xiao will reboot. Your computer should now enumerate **two** USB serial ports for it.

### 2. Open the web app

Serve `index.html` from a local HTTP server (required for Web Serial):

```bash
python3 -m http.server
```

Then open `http://localhost:8000/index.html` in Chrome or Edge.

### 3. Connect to the Xiao

Click **Connect Serial** and select the **second** serial port (the data port, not the REPL console). The status indicator should show **Idle**.

### 4. Pair with your target device

1. On your target device, open Bluetooth settings and make it discoverable (or start scanning).
2. Click **Pair BLE** in the web app. The Xiao will start advertising as `ForwardHID`.
3. On the target device, connect to `ForwardHID`. Accept the pairing if prompted.
4. The status indicator in the web app should change to **Connected** with the device name.

## Usage

### Settings

| Setting | Description |
|---------|-------------|
| Resolution (W × H) | Screen resolution of the **target device** (e.g., 2360×1640 for iPad Pro 12.9"). This sets the mirror area's aspect ratio. |
| Mirror width | Pixel width of the mirror area in your browser. Height is computed automatically. |

### Mouse mirror area

- **Move** your cursor inside the area → cursor moves on the target device
- **Click** (left, right, or middle) inside the area → click is forwarded
- **Scroll** inside the area → scroll is forwarded
- **Type** while the mirror area is focused (click it first if needed) → keystrokes are forwarded

Move your cursor **outside** the mirror area to return control to your own computer. All held keys and buttons are automatically released when the cursor leaves.

### Notes

- Some browser shortcuts (Cmd+W, Cmd+Q, etc.) cannot be intercepted by the web app. Avoid pressing them while using the mirror area.
- The keycode map assumes a **US QWERTY** physical keyboard layout.
- If the target device disconnects, click **Pair BLE** again to reconnect.

## Troubleshooting

| Problem | Solution |
|---------|---------|
| Only one serial port appears | Make sure `boot.py` is in the CIRCUITPY root and the Xiao has rebooted |
| "Connect Serial" button does nothing | Use Chrome or Edge; Firefox and Safari don't support Web Serial |
| Web Serial blocked | Serve via `python3 -m http.server` and open `localhost`, not `file://` |
| Cursor doesn't move on target | Confirm BLE is connected (status shows device name); try re-pairing |
| Wrong characters typed | Check that the target device's keyboard layout is set to US English |
| Device not visible in BLE scan | Click "Pair BLE" again; the device only advertises when triggered |

## Project Structure

```
keyboard-forward/
├── README.md       ← this file
├── CLAUDE.md       ← technical reference
├── design.md       ← full design spec
├── index.html      ← web app (open in Chrome/Edge)
└── firmware/
    ├── boot.py     ← copy to CIRCUITPY root
    └── code.py     ← copy to CIRCUITPY root
```
