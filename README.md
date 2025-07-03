
https://github.com/user-attachments/assets/f1880a8a-0d44-4be8-ac98-36fd05764d17

I wrote this script with Grok-3 using ALSA backend and WineASIO for FL Studio which runs over Jack. However Jack devices don't show up in Wine, and FL Studio can't deal with MIDI-Channels in Midi Through it needs one ALSA device per "port". Then snd-virtmidi and all sorts of other solutions to this were totally bugged and not usable.

This is why there are 3 scripts: Two are responsible for spawning the virtual ALSA devices as a daemon. And the main script then just sends the MIDI scores to those. 

Then you can map the virtual devices in Wine or elsewhere to your synths.

### Installation & Running

1. Install **rtmidi** and **mididings** via pip or package manager
2. put 2spawnmidi and 2spawnmidiports into /usr/local/bin/
3. run 2spawnmidi in background, e.g. with "screen 2spawnmidiports"
4. launch Wine or DAW and set up routing to your synths
5. run acid2midi.py
