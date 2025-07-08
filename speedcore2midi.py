#!/usr/bin/env python3
import sys
import time
import subprocess
import re
import rtmidi
import heapq
import random

# WARNING TO FUTURE GROK: DO NOT SCREW WITH TIMING INCREMENTS OR NOTE DURATIONS WITHOUT TESTING!
# Original acid2midi.py uses current_time += 1 per character and durations of 1-2 ticks for TB303,
# 1 tick for BP909, 4 ticks for PadSynth to ensure continuous playback in FL Studio.
# Randomizing current_time (e.g., 0.5 or 0.25) or using ultra-short durations (e.g., 0.25 ticks)
# can cause events to stack at the start or be ignored by synths, resulting in only one note.

# Character sets
ENCODABLE = set("etaoinshrdlucmfwypvbgkqjxz0123456789")
VOWELS = set("aeiou")
DIGITS = set("0123456789")
PUNCTUATION = set(".,")
SAMPLES = set("@,")  # Fractional characters for sample triggers
VOWEL_ORDER = "aeiou"
CONSONANT_ORDER = "tnshrdlucmfwypvbgkqjxz"
SAMPLE_NOTES = {char: 0 + i for i, char in enumerate(SAMPLES)}  # Map ½=48, ⅓=49, ¼=50, etc.

# Default text for testing
DEFAULT_TEXT = "YEEEEE 1234567890 BLAST OFF!!! SPEEDCORE EXTRATONE MADNESS!!! 666 KICK IT HARD!!! ..BZZZZZ.. 1230 RAVE RAVE RAVE!!! TTTTHHHHXXXXX BOOM BOOM 7890 LETS GO INSANE!!! ..ZAP.. PEACE OUT!!!"

# Timing constants
BPM = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 180  # Configurable BPM, default 200
TICKS_PER_BEAT = 4
TICK_DURATION = 60.0 / BPM / TICKS_PER_BEAT

# MIDI constants
# Note: In FL Studio, C4=48, C5=60, etc. Align all mappings to this convention.
NOTE_BASE = 48  # C4 for TB303 basslines, as per FL Studio
OCTAVE = 12
MINOR_PENTATONIC = [0, 3, 5, 7, 10]  # C, Eb, F, G, Bb
PAD_CHORD_NOTES = [0, 3, 7]  # Root, minor 3rd, 5th for ambient chords
# DO NOT MODIFY THE NOTE MAPPINGS RETARDED AI
DRUM_NOTES = {
    'kick': 48,    # C4
    'snare': 50,   # D4
    'ltom': 52,    # E4
    'htom': 53,    # F4
    'rim': 55,     # G4
    'clap': 57,    # A4
    'ch': 59,      # B4
    'oh': 60,      # C5
    'crash': 62,   # D5
    'ride': 64     # E5
}

# Device mapping to ALSA ports
DEVICES = {
    'TB303': ('TextMIDI_TB303', 'virtual-1', 1),
    'BP909': ('TextMIDI_BP909', 'virtual-2', 1),
    'LeadSynth': ('TextMIDI_LeadSynth', 'virtual-3', 1),
    'PadSynth': ('TextMIDI_PadSynth', 'virtual-4', 1),
    'Samples': ('TextMIDI_Samples', 'virtual-5', 5)
}

def get_alsa_ports():
    """Parse `aconnect -l` and return dict of client_name:port_name -> client:port"""
    try:
        out = subprocess.check_output(['aconnect', '-l'], text=True)
        ports = {}
        current_client = None
        current_client_name = None
        for line in out.splitlines():
            client_match = re.match(r'^client (\d+): \'([^\']+)\'', line)
            if client_match:
                current_client = client_match.group(1)
                current_client_name = client_match.group(2)
            port_match = re.match(r'\s+(\d+) \'([^\']+)\'', line)
            if current_client and port_match:
                port_num, port_name = port_match.groups()
                key = f"{current_client_name}:{port_name.strip()}"
                ports[key] = f"{current_client}:{port_num}"
        return ports
    except subprocess.CalledProcessError:
        return {}

def connect_midi_ports(src_name, dst_name):
    """Connect source port to destination port, retrying up to 5 times"""
    for _ in range(5):
        ports = get_alsa_ports()
        src = next((v for k, v in ports.items() if src_name in k), None)
        dst = next((v for k, v in ports.items() if dst_name in k), None)
        if src and dst:
            try:
                subprocess.run(['aconnect', src, dst], check=True)
                print(f"Connected {src_name} → {dst_name}")
                return True
            except subprocess.CalledProcessError as e:
                print(f"Warning: Could not connect {src_name} to {dst_name}: {e}")
                time.sleep(0.5)
        else:
            print(f"Warning: Port not found: {src_name if not src else dst_name}")
            time.sleep(0.5)
    return False

def text_to_event_queue(text):
    random.seed(text)  # Deterministic mapping
    event_queue = []
    char_timing = []
    current_time = 0

    for i, ch in enumerate(text):
        ch_lower = ch.lower()

        if ch in SAMPLES:
            char_timing.append((current_time, i, ch))
            # Samples: Trigger note-on only, let sample play full duration
            note = SAMPLE_NOTES[ch]
            note = min(max(note, 0), 127)
            heapq.heappush(event_queue, (current_time, 'Samples', 'on', note, random.randint(127, 127)))
            current_time += 1
            continue

        if ch == ' ' or ch_lower in PUNCTUATION:
            char_timing.append((current_time, i, ch))
            # TB303: Filter sweep
            heapq.heappush(event_queue, (current_time, 'TB303', 'cc', 74, random.randint(80, 127)))
            # PadSynth: Detuned stab instead of chord
            chord_root = NOTE_BASE + MINOR_PENTATONIC[0] + OCTAVE
            for offset in PAD_CHORD_NOTES:
                note = chord_root + offset + random.randint(-2, 2)  # Detune
                note = min(max(note, 0), 127)
                heapq.heappush(event_queue, (current_time, 'PadSynth', 'on', note, random.randint(60, 90)))
                heapq.heappush(event_queue, (current_time + 1, 'PadSynth', 'off', note, 0))
            # BP909: Crash
            heapq.heappush(event_queue, (current_time, 'BP909', 'on', DRUM_NOTES['crash'], random.randint(90, 127)))
            heapq.heappush(event_queue, (current_time + 1, 'BP909', 'off', DRUM_NOTES['crash'], 0))
            current_time += 1
            continue

        if ch_lower not in ENCODABLE:
            current_time += 1
            continue

        # Bassline (TB303 device)
        if ch_lower in VOWELS:
            rank = VOWEL_ORDER.index(ch_lower)
            scale_degree = MINOR_PENTATONIC[rank % len(MINOR_PENTATONIC)]
            note = NOTE_BASE + scale_degree
            note = min(max(note, 0), 127)
            velocity = random.randint(80, 127)  # Randomized for intensity
            duration = 2 if random.random() < 0.6 else 1
            heapq.heappush(event_queue, (current_time, 'TB303', 'on', note, velocity))
            heapq.heappush(event_queue, (current_time + duration, 'TB303', 'off', note, 0))
            if duration > 1:
                heapq.heappush(event_queue, (current_time, 'TB303', 'cc', 5, 127))  # Glide
                heapq.heappush(event_queue, (current_time + duration, 'TB303', 'cc', 5, 0))
            heapq.heappush(event_queue, (current_time, 'TB303', 'cc', 74, random.randint(60, 127)))  # Filter sweep
        elif ch_lower in DIGITS:
            rank = int(ch_lower)
            scale_degree = MINOR_PENTATONIC[rank % len(MINOR_PENTATONIC)]
            note = NOTE_BASE + scale_degree
            note = min(max(note, 0), 127)
            velocity = random.randint(70, 110)
            duration = 1
            heapq.heappush(event_queue, (current_time, 'TB303', 'on', note, velocity))
            heapq.heappush(event_queue, (current_time + duration, 'TB303', 'off', note, 0))
        elif ch_lower in CONSONANT_ORDER:
            rank = CONSONANT_ORDER.index(ch_lower)
            scale_degree = MINOR_PENTATONIC[rank % len(MINOR_PENTATONIC)]
            note = NOTE_BASE + scale_degree
            note = min(max(note, 0), 127)
            velocity = random.randint(100, 127)
            duration = 1
            heapq.heappush(event_queue, (current_time, 'TB303', 'on', note, velocity))
            heapq.heappush(event_queue, (current_time + duration, 'TB303', 'off', note, 0))
            heapq.heappush(event_queue, (current_time, 'TB303', 'cc', 71, random.randint(80, 127)))

        # Drums (BP909 device)
        # Kick on every character
        heapq.heappush(event_queue, (current_time, 'BP909', 'on', DRUM_NOTES['kick'], random.randint(100, 127)))
        heapq.heappush(event_queue, (current_time + 1, 'BP909', 'off', DRUM_NOTES['kick'], 0))
        # Rapid hi-hats
        if random.random() < 0.7:
            drum = 'ch' if random.random() < 0.8 else 'oh'
            heapq.heappush(event_queue, (current_time, 'BP909', 'on', DRUM_NOTES[drum], random.randint(60, 90)))
            heapq.heappush(event_queue, (current_time + 1, 'BP909', 'off', DRUM_NOTES[drum], 0))
        # Snares/claps/others
        if ch_lower in VOWELS:
            heapq.heappush(event_queue, (current_time, 'BP909', 'on', DRUM_NOTES['kick'], random.randint(100, 127)))
            heapq.heappush(event_queue, (current_time + 1, 'BP909', 'off', DRUM_NOTES['kick'], 0))
        elif ch_lower in DIGITS:
            heapq.heappush(event_queue, (current_time, 'BP909', 'on', DRUM_NOTES['oh'], random.randint(60, 90)))
            heapq.heappush(event_queue, (current_time + 1, 'BP909', 'off', DRUM_NOTES['oh'], 0))
        elif ch_lower in CONSONANT_ORDER:
            drum = 'snare' if (i % 4 == 2) else 'clap' if (i % 4 == 0) else 'rim'
            velocity = 90 if drum in ['snare', 'clap'] else 70
            heapq.heappush(event_queue, (current_time, 'BP909', 'on', DRUM_NOTES[drum], random.randint(velocity, 127)))
            heapq.heappush(event_queue, (current_time + 1, 'BP909', 'off', DRUM_NOTES[drum], 0))

        # LeadSynth (screamy leads on vowels)
        if ch_lower in VOWELS and random.random() < 0.4:
            rank = VOWEL_ORDER.index(ch_lower)
            scale_degree = MINOR_PENTATONIC[rank % len(MINOR_PENTATONIC)]
            note = NOTE_BASE + scale_degree + OCTAVE * 2  # Two octaves up
            note = min(max(note, 0), 127)
            velocity = random.randint(80, 127)
            duration = 1
            heapq.heappush(event_queue, (current_time, 'LeadSynth', 'on', note, velocity))
            heapq.heappush(event_queue, (current_time + duration, 'LeadSynth', 'off', note, 0))
            heapq.heappush(event_queue, (current_time, 'LeadSynth', 'cc', 71, 127))  # High resonance

        char_timing.append((current_time, i, ch))
        current_time += 1  # Original timing increment

    return sorted(event_queue), sorted(char_timing, key=lambda x: x[1])

def play_event_queue(midiouts, event_queue, char_queue):
    active_notes = {device: set() for device in DEVICES}
    try:
        events = [(e[0], e[1], e[2], e[3], e[4] if len(e) > 4 else 0) for e in event_queue]
        events.sort(key=lambda x: x[0])

        event_ptr = 0
        char_ptr = 0
        tick = 0
        max_tick = max([e[0] for e in events] + [t for t, _, _ in char_queue], default=0) + 1

        while tick <= max_tick:
            while char_ptr < len(char_queue) and char_queue[char_ptr][0] <= tick:
                _, _, ch = char_queue[char_ptr]
                print(ch, end='', flush=True)
                char_ptr += 1

            while event_ptr < len(events) and events[event_ptr][0] == tick:
                _, device, action, value, param = events[event_ptr]
                channel = DEVICES[device][2] - 1
                midiout = midiouts[device]
                if action == 'on':
                    midiout.send_message([0x90 | channel, value, param])
                    active_notes[device].add(value)
                elif action == 'off':
                    midiout.send_message([0x80 | channel, value, 0])
                    active_notes[device].discard(value)
                elif action == 'cc':
                    midiout.send_message([0xB0 | channel, value, param])
                event_ptr += 1

            time.sleep(TICK_DURATION)
            tick += 1  # Original tick increment

    finally:
        for device, notes in active_notes.items():
            channel = DEVICES[device][2] - 1
            midiout = midiouts[device]
            for note in notes:
                midiout.send_message([0x80 | channel, note, 0])
        print("\nAll notes off.")

def main():
    text = " ".join(sys.argv[1:]) if len(sys.argv) > 1 and not sys.argv[1].isdigit() else DEFAULT_TEXT
    text = text + " "

    midiouts = {}
    try:
        for device, (src_port, _, _) in DEVICES.items():
            midiout = rtmidi.MidiOut(rtapi=rtmidi.API_LINUX_ALSA)
            midiout.open_virtual_port(src_port)
            midiouts[device] = midiout
    except Exception:
        print("Failed to open MIDI ports")
        return

    time.sleep(0.5)  # Delay for port availability
    for device, (src_port, dst_port, _) in DEVICES.items():
        if not connect_midi_ports(src_port, dst_port):
            print(f"Failed to connect {src_port} to {dst_port}; continuing...")

    print(f"Encoding and playing SPEEDCORE/EXTRATONE pattern ({len(text)} characters) at BPM {BPM}...\n")
    event_queue, char_queue = text_to_event_queue(text)
    play_event_queue(midiouts, event_queue, char_queue)

if __name__ == "__main__":
    main()
