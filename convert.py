import sys, os, argparse
import numpy as np
from pydub import AudioSegment
from scipy.signal import resample_poly
from math import gcd

TARGET = 8000

def convert(inp, out):
    seg = AudioSegment.from_file(inp)
    sr = seg.frame_rate
    ch = seg.channels
    samples = np.array(seg.get_array_of_samples(), dtype=np.float32)
    if ch > 1:
        samples = samples.reshape(-1, ch).mean(axis=1)
    samples /= float(1 << (seg.sample_width * 8 - 1))
    if sr != TARGET:
        g = gcd(sr, TARGET)
        samples = resample_poly(samples, TARGET // g, sr // g).astype(np.float32)
    samples = np.clip(samples, -1.0, 1.0)
    raw = (samples * 32767).astype(np.int16).tobytes()
    with open(out, "wb") as f:
        f.write(raw)
    print(f"{out}: {len(raw)}B ({len(raw)/16000:.1f}s)")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("i"); ap.add_argument("o", nargs="?")
    a = ap.parse_args()
    if not os.path.isfile(a.i): print(f"not found: {a.i}"); sys.exit(1)
    convert(a.i, a.o or os.path.splitext(a.i)[0] + ".raw")
