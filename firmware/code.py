import struct
import time
import usb_cdc
from adafruit_ble import BLERadio
from adafruit_ble.advertising.standard import ProvideServicesAdvertisement
from adafruit_ble.services.standard.hid import HIDService

# fmt: off
HID_DESCRIPTOR = bytes([
    # === Report ID 1: Keyboard ===
    0x05, 0x01, 0x09, 0x06, 0xA1, 0x01,
    0x85, 0x01,
    0x05, 0x07, 0x19, 0xE0, 0x29, 0xE7,
    0x15, 0x00, 0x25, 0x01, 0x75, 0x01, 0x95, 0x08, 0x81, 0x02,
    0x75, 0x08, 0x95, 0x01, 0x81, 0x01,
    0x05, 0x08, 0x19, 0x01, 0x29, 0x05,
    0x75, 0x01, 0x95, 0x05, 0x91, 0x02,
    0x75, 0x03, 0x95, 0x01, 0x91, 0x01,
    0x05, 0x07, 0x19, 0x00, 0x29, 0xFF,
    0x15, 0x00, 0x26, 0xFF, 0x00, 0x75, 0x08, 0x95, 0x06, 0x81, 0x00,
    0xC0,
    # === Report ID 2: Absolute Mouse ===
    0x05, 0x01, 0x09, 0x02, 0xA1, 0x01,
    0x85, 0x02,
    0x09, 0x01, 0xA1, 0x00,
    0x05, 0x09, 0x19, 0x01, 0x29, 0x03,
    0x15, 0x00, 0x25, 0x01, 0x75, 0x01, 0x95, 0x03, 0x81, 0x02,
    0x75, 0x05, 0x95, 0x01, 0x81, 0x01,
    0x05, 0x01, 0x09, 0x30,
    0x15, 0x00, 0x26, 0xFF, 0x7F, 0x75, 0x10, 0x95, 0x01, 0x81, 0x02,
    0x09, 0x31,
    0x15, 0x00, 0x26, 0xFF, 0x7F, 0x75, 0x10, 0x95, 0x01, 0x81, 0x02,
    0x09, 0x38,
    0x15, 0x81, 0x25, 0x7F, 0x75, 0x08, 0x95, 0x01, 0x81, 0x06,
    0xC0, 0xC0,
])
# fmt: on

# Payload bytes following each command byte (not counting the command byte itself)
CMD_SIZES = {0x01: 0, 0x02: 6, 0x03: 2, 0x04: 2, 0x05: 0, 0x06: 1}


class KbdState:
    def __init__(self, dev):
        self._dev = dev
        self._report = bytearray(8)  # [modifier, reserved, key0..key5]

    def key_down(self, modifier, keycode):
        self._report[0] |= modifier
        if keycode:
            already_held = False
            for i in range(2, 8):
                if self._report[i] == keycode:
                    already_held = True
                    break
            if not already_held:
                for i in range(2, 8):
                    if self._report[i] == 0:
                        self._report[i] = keycode
                        break
        self._send()

    def key_up(self, modifier, keycode):
        self._report[0] &= ~modifier & 0xFF
        if keycode:
            for i in range(2, 8):
                if self._report[i] == keycode:
                    self._report[i] = 0
                    break
        self._send()

    def release_all(self):
        for i in range(8):
            self._report[i] = 0
        self._send()

    def _send(self):
        try:
            self._dev.send_report(self._report)
        except Exception as e:
            print("KBD ERR", type(e).__name__, e)


class MouseState:
    def __init__(self, dev):
        self._dev = dev
        self.buttons = 0
        self.x = 0
        self.y = 0

    def move(self, buttons, x, y, wheel):
        self.buttons = buttons
        self.x = x
        self.y = y
        self._send(wheel)

    def set_buttons(self, buttons):
        self.buttons = buttons
        self._send(0)

    def _send(self, wheel=0):
        try:
            self._dev.send_report(struct.pack("<BHHb", self.buttons, self.x, self.y, wheel))
        except Exception as e:
            print("MSE ERR", type(e).__name__, e)


# Serial receive buffer — handles fragmented USB CDC reads
_buf = bytearray(32)
_buf_len = 0
_pending_cmd = None
_pending_need = 0


def poll_serial(serial, dispatch):
    global _buf, _buf_len, _pending_cmd, _pending_need

    available = serial.in_waiting
    if available:
        chunk = serial.read(min(available, len(_buf) - _buf_len))
        n = len(chunk)
        _buf[_buf_len : _buf_len + n] = chunk
        _buf_len += n

    while True:
        if _pending_cmd is None:
            if _buf_len < 1:
                break
            cmd = _buf[0]
            _buf[0 : _buf_len - 1] = _buf[1 : _buf_len]
            _buf_len -= 1
            if cmd not in CMD_SIZES:
                continue
            _pending_cmd = cmd
            _pending_need = CMD_SIZES[cmd]

        if _buf_len < _pending_need:
            break

        payload = bytes(_buf[: _pending_need])
        _buf[0 : _buf_len - _pending_need] = _buf[_pending_need : _buf_len]
        _buf_len -= _pending_need
        dispatch[_pending_cmd](payload)
        _pending_cmd = None
        _pending_need = 0


# BLE + HID setup
ble = BLERadio()
ble.name = "ForwardHID"
hid = HIDService(hid_descriptor=HID_DESCRIPTOR)
advertisement = ProvideServicesAdvertisement(hid)

# hid.devices order matches descriptor Report ID order: [0]=keyboard, [1]=mouse
print("hid.devices:", len(hid.devices))
for _i, _d in enumerate(hid.devices):
    print(" [" + str(_i) + "]", type(_d).__name__,
          "up=" + str(getattr(_d, "usage_page", "?")),
          "u=" + str(getattr(_d, "usage", "?")))

kbd_device = hid.devices[0]
mouse_device = hid.devices[1]

kbd = KbdState(kbd_device)
mouse = MouseState(mouse_device)

serial = usb_cdc.data
state = "IDLE"
_conn_time = 0


def send_status(msg):
    try:
        serial.write((msg + "\n").encode())
    except Exception:
        pass


def cmd_advertise():
    global state
    if state not in ("CONN", "WAIT", "ADV"):
        ble.start_advertising(advertisement)
        state = "ADV"
        send_status("ADV")


def cmd_mouse_move(payload):
    if state == "CONN":
        buttons = payload[0]
        x = payload[1] | (payload[2] << 8)
        y = payload[3] | (payload[4] << 8)
        raw_wheel = payload[5]
        wheel = raw_wheel if raw_wheel < 128 else raw_wheel - 256
        mouse.move(buttons, x, y, wheel)


def cmd_key_down(payload):
    if state == "CONN":
        kbd.key_down(payload[0], payload[1])


def cmd_key_up(payload):
    if state == "CONN":
        kbd.key_up(payload[0], payload[1])


def cmd_release_all(_payload):
    if state == "CONN":
        kbd.release_all()


def cmd_mouse_buttons(payload):
    if state == "CONN":
        mouse.set_buttons(payload[0])


DISPATCH = {
    0x01: lambda p: cmd_advertise(),
    0x02: cmd_mouse_move,
    0x03: cmd_key_down,
    0x04: cmd_key_up,
    0x05: cmd_release_all,
    0x06: cmd_mouse_buttons,
}


def poll_ble():
    global state, _conn_time
    if state == "ADV" and ble.connected:
        # Give iOS time to discover services and subscribe to HID notifications
        # before we start sending reports.
        _conn_time = time.monotonic()
        state = "WAIT"
        try:
            name = ble._connections[0]._connection._remote_name or "Unknown"
        except Exception:
            name = "Unknown"
        print("BLE connected, waiting for HID setup:", name)
        send_status("CONN:" + name)
    elif state == "WAIT" and time.monotonic() - _conn_time >= 2.0:
        state = "CONN"
        print("HID ready")
    elif state in ("CONN", "WAIT") and not ble.connected:
        state = "IDLE"
        kbd.release_all()
        send_status("DISC")


send_status("IDLE")

while True:
    poll_serial(serial, DISPATCH)
    poll_ble()
