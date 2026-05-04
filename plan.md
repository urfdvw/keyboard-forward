# keyboard forward

- hardware: Xiao nrf52840
- firmware: CircuitPython 10.2

## Current Goal

Use the Xiao as a BLE keyboard bridge that forwards keyboard input from the host computer to another device.

## Firmware

- The Xiao acts as a BLE HID keyboard.
- It uses `HIDService()` plus `adafruit_hid.keyboard.Keyboard`.
- It receives binary keyboard commands over `usb_cdc.data`.
- Serial commands also control when BLE advertising starts.
- BLE status is reported back over serial as `IDLE`, `ADV`, `CONN:<name>`, and `DISC`.
- Modifier state is synchronized from the host's full modifier bitmask.

## Host App

- single-file HTML page
- uses Web Serial to talk to the Xiao
- current UI:
  - serial connect
  - BLE pair
  - live keyboard capture toggle
  - send-text textarea

## Current Input Flow

- The host app connects to the Xiao over Web Serial.
- When capture mode is enabled, global `keydown` and `keyup` events are forwarded.
- The page can also send ASCII text by converting characters into HID keycode plus modifier pairs.
- The firmware converts those packets into BLE keyboard actions on the paired target device.

## Current Scope

- Keyboard forwarding is in scope.
- Mouse forwarding is not implemented in the current firmware revision.
