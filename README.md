# Traptanium Audio Player

plays audio through the skylanders trap team portal speaker over usb, no game needed

---

## what's this

so the trap team portal is the only skylanders portal that actually has a speaker in it. the game uses it to play villain voices out of the portal itself which is pretty cool. this just lets you send whatever audio you want through it from your pc.

most of the actual hard work was done by marijn kneppers who reverse engineered the whole usb protocol. i just wrote a python script on top of it.

---

## requirements

you need the trap team portal specifically (the traptanium one). spyro's adventure, giants, superchargers etc don't have speakers so they won't work.

- python 3.10+

pip install -r requirements.txt

---

## files

| file | what it does |
|---|---|
| `convert.py` | converts a wav to the raw pcm format the portal wants |
| `portalaudio.py` | streams a `.raw` file to the portal |
| `requirements.txt` | dependencies |

---

## how to use

**step 1 - convert your audio**

python convert.py input.wav

spits out `input.raw` (mono, 16-bit, 8000hz pcm). resamples automatically if needed. if you're starting from an mp3 just convert to wav with ffmpeg first:

ffmpeg -i input.mp3 input.wav

**step 2 - play it**

python portalaudio.py input.raw

optional flags:

| flag | what it does |
|---|---|
| `--mode hid` | sends `0x00` + 64-byte hid reports instead of raw 64-byte writes |
| `--debug` | prints every chunk as it sends |

---

## how it works

the portal is just a usb hid device (vid `0x1430`, pid `0x0150`, same across all skylanders portals). you send 32-byte command packets over the out endpoint where the first byte is an ascii command character, and it sends back `0x53` status packets.

to actually play audio you:
1. send `R` to wake it up
2. send `A 01` to activate
3. send `M 01` to turn the speaker on
4. stream 64-byte audio chunks at about 4ms each (8000hz)
5. send `M 00` when done

if it plays as loud noise instead of actual audio it's a byte order issue, can differ between firmware versions.

---

## credits

marijn kneppers did all the reverse engineering, seriously go read his writeup it's really cool

- writeup: https://marijnkneppers.dev/posts/reverse-engineering-skylanders-toys-to-life-mechanics/
- his c# implementation: https://github.com/mandar1jn/SkylandersToolkit
- wireshark dissector: https://github.com/pop-emu/portal-dissector

---

## notes

- built and tested on windows 11, linux/mac untested
- if it's not detecting the portal make sure the skylanders game isn't open, it'll hold onto the hid handle
