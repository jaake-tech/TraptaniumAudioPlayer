import sys, os, time, argparse, threading, array, struct, math

import usb.backend.libusb1
_backend = usb.backend.libusb1.get_backend(find_library=lambda x: os.path.expanduser(
    r'~\AppData\Local\Programs\Python\Python311\Lib\site-packages\libusb\_platform\windows\x86_64\libusb-1.0.dll'))
import usb.core, usb.util

VID, PID = 0x1430, 0x0150
CHUNK, RATE, BPS = 64, 8000, 2
CHUNK_DUR = CHUNK / (RATE * BPS)

CMD_SZ = 32
CMD_R, CMD_A, CMD_M, CMD_C = ord('R'), ord('A'), ord('M'), ord('C')
CTRL = 0x21

class Portal:
    def __init__(self, dev, ep_in, iface, ep_out=None):
        self.dev = dev; self.ep_in = ep_in; self.ep_out = ep_out; self.iface = iface
    def cmd(self, p, t=1000):
        try: self.dev.ctrl_transfer(CTRL, 0x09, 0x0200, self.iface, p, timeout=t)
        except usb.core.USBError as e: raise IOError(f"cmd: {e}")
    def write(self, p, t=1000):
        try:
            if self.ep_out: self.ep_out.write(p, timeout=t)
            else: self.cmd(p, t)
        except usb.core.USBError as e: raise IOError(f"write: {e}")
    def read(self, t=100):
        try: return bytes(self.ep_in.read(self.ep_in.wMaxPacketSize, timeout=t)) or None
        except: return None
    def close(self):
        try: usb.util.dispose_resources(self.dev)
        except: pass

def pkt(*b):
    buf = bytearray(CMD_SZ)
    for i, v in enumerate(b):
        if i < CMD_SZ: buf[i] = v & 0xFF
    return bytes(buf)

def resp(p, exp, t=1000):
    deadline = time.monotonic() + t / 1000
    while time.monotonic() < deadline:
        r = p.read(max(1, int((deadline - time.monotonic()) * 1000)))
        if r and r[0] == exp: return r

def ready(p):
    p.cmd(pkt(CMD_R))
    if not resp(p, CMD_R): raise IOError("no response")

def activate(p, on=True):
    p.cmd(pkt(CMD_A, 0x01 if on else 0x00))
    return resp(p, CMD_A)

def music(p, on=True):
    p.cmd(pkt(CMD_M, 0x01 if on else 0x00))
    return resp(p, CMD_M, 2000)

def color(p, r, g, b):
    p.cmd(pkt(CMD_C, r, g, b))

def open_portal():
    dev = usb.core.find(idVendor=VID, idProduct=PID, backend=_backend)
    if not dev: raise IOError("Portal not found. Run Zadig and bind to WinUSB.")
    try: dev.set_configuration()
    except: pass
    intf = dev.get_active_configuration()[(0, 0)]
    try: usb.util.claim_interface(dev, intf.bInterfaceNumber)
    except: pass
    ep_in = usb.util.find_descriptor(intf, custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_IN)
    ep_out = usb.util.find_descriptor(intf, custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_OUT)
    if not ep_in: raise IOError("no IN endpoint")
    return Portal(dev, ep_in, intf.bInterfaceNumber, ep_out)

class Drainer:
    def __init__(self, p):
        self.p = p; self._s = threading.Event(); self._t = threading.Thread(target=self._run, daemon=True)
    def start(self): self._t.start()
    def stop(self): self._s.set(); self._t.join(1)
    def _run(self):
        while not self._s.is_set():
            try: self.p.read(20)
            except: break
            time.sleep(0.005)

def scale(pcm, f):
    if f == 1.0: return pcm
    s = array.array('h')
    s.frombytes(pcm if not len(pcm) % 2 else pcm + b'\x00')
    for i in range(len(s)):
        v = int(s[i] * f); s[i] = max(-32768, min(32767, v))
    return s.tobytes()

def swap(pcm):
    ba = bytearray(pcm)
    if len(ba) % 2: ba.append(0)
    ba[0::2], ba[1::2] = ba[1::2], ba[0::2]
    return bytes(ba)

def stream(p, audio, vol=1.0, be=False, viz=True):
    audio = scale(audio, vol)
    if be: audio = swap(audio)
    n = (len(audio) + CHUNK - 1) // CHUNK
    dur = len(audio) / (RATE * BPS)
    print(f"  {n}c | {dur:.1f}s | vol={vol} | {'BE' if be else 'LE'}")
    pref, start = 10, time.monotonic()
    for i in range(n):
        c = audio[i * CHUNK:(i + 1) * CHUNK]
        if len(c) < CHUNK: c += bytes(CHUNK - len(c))
        p.write(c)
        if viz and i > 0 and i % 16 == 0:
            w = audio[max(0, (i - 16) * CHUNK):i * CHUNK]
            if w:
                ns = len(w) // 2
                rms = math.sqrt(sum(v * v for v in struct.unpack('<' + str(ns) + 'h', w[:ns * 2]))) / ns / 32767
                if rms < 0.1: color(p, 0, int(55 * rms / 0.1), int(255 * (1 - rms / 0.1)))
                elif rms < 0.3: color(p, int(255 * (rms - 0.1) / 0.2), 255, 0)
                else: color(p, 255, max(0, int(255 * (1 - (rms - 0.3) / 0.7))), 0)
        if i >= pref:
            t = start + (i - pref) * CHUNK_DUR
            n2 = time.monotonic()
            if t > n2: time.sleep(t - n2)

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("f")
    ap.add_argument("--v", type=float, default=1.0)
    ap.add_argument("--be", action="store_true")
    ap.add_argument("--no-viz", action="store_true")
    a = ap.parse_args()
    if not os.path.exists(a.f): print(f"not found: {a.f}"); sys.exit(1)
    with open(a.f, "rb") as f: audio = f.read()
    print(f"{len(audio)}B ({len(audio)/16000:.1f}s)")
    p = open_portal()
    try:
        for _ in range(20):
            if p.read(20) is None: break
        ready(p); activate(p, True); music(p, True); color(p, 0, 255, 0)
        d = Drainer(p); d.start()
        stream(p, audio, vol=a.v, be=a.be, viz=not a.no_viz)
        d.stop()
    except KeyboardInterrupt: print()
    except Exception as e: print(f"err: {e}")
    finally:
        try: color(p, 0, 0, 0); music(p, False); activate(p, False)
        except: pass
        p.close()
