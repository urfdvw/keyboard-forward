import time
import usb_cdc
from adafruit_ble import BLERadio
from adafruit_ble.advertising.standard import ProvideServicesAdvertisement
from adafruit_ble.services.standard.hid import HIDService
from adafruit_hid.keyboard import Keyboard

CMD_SIZES = {0x01: 0, 0x03: 2, 0x04: 2, 0x05: 0}

ble = BLERadio()
ble.name = "ForwardHID"
hid = HIDService()
advertisement = ProvideServicesAdvertisement(hid)
keyboard = Keyboard(hid.devices)  # finds the correct HID device automatically

serial = usb_cdc.data
state = "IDLE"
_conn_time = 0
_current_mod = 0  # tracks modifier byte in sync with keyboard.report[0]

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


def send_status(msg):
    try:
        serial.write((msg + "\n").encode())
    except Exception:
        pass


def _apply_mod(new_mod):
    # Sync modifier keys: host sends full current modifier bitmask.
    # Bit i maps to keycode 0xE0+i (L-Ctrl, L-Shift, L-Alt, L-GUI, R-Ctrl, R-Shift, R-Alt, R-GUI).
    global _current_mod
    diff = _current_mod ^ new_mod
    for i in range(8):
        bit = 1 << i
        if diff & bit:
            try:
                if new_mod & bit:
                    keyboard.press(0xE0 + i)
                else:
                    keyboard.release(0xE0 + i)
            except Exception as e:
                print("MOD ERR", e)
    _current_mod = new_mod


def cmd_advertise():
    global state
    if state not in ("CONN", "WAIT", "ADV"):
        ble.start_advertising(advertisement)
        state = "ADV"
        send_status("ADV")


def cmd_key_down(payload):
    print("KEY_DOWN state=%s mod=%02x kc=%02x" % (state, payload[0], payload[1]))
    if state == "CONN":
        _apply_mod(payload[0])
        if payload[1]:
            try:
                keyboard.press(payload[1])
                print("press ok")
            except Exception as e:
                print("KBD ERR", e)


def cmd_key_up(payload):
    print("KEY_UP state=%s mod=%02x kc=%02x" % (state, payload[0], payload[1]))
    if state == "CONN":
        if payload[1]:
            try:
                keyboard.release(payload[1])
            except Exception as e:
                print("KBD ERR", e)
        _apply_mod(payload[0])


def cmd_release_all(_payload):
    global _current_mod
    if state == "CONN":
        keyboard.release_all()
        _current_mod = 0


DISPATCH = {
    0x01: lambda p: cmd_advertise(),
    0x03: cmd_key_down,
    0x04: cmd_key_up,
    0x05: cmd_release_all,
}


def poll_ble():
    global state, _conn_time, _current_mod
    if state == "ADV" and ble.connected:
        _conn_time = time.monotonic()
        state = "WAIT"
        try:
            name = ble._connections[0]._connection._remote_name or "Unknown"
        except Exception:
            name = "Unknown"
        send_status("CONN:" + name)
    elif state == "WAIT" and time.monotonic() - _conn_time >= 2.0:
        state = "CONN"
        print("entered CONN state")
    elif state in ("CONN", "WAIT") and not ble.connected:
        state = "IDLE"
        _current_mod = 0
        keyboard.release_all()
        send_status("DISC")


send_status("IDLE")

while True:
    poll_serial(serial, DISPATCH)
    poll_ble()
