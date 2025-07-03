#!/usr/bin/env python3
import sys
import time
import subprocess
import re
import rtmidi
import heapq
import random

# Character sets
ENCODABLE = set("etaoinshrdlucmfwypvbgkqjxz0123456789")
VOWELS = set("aeiou")
DIGITS = set("0123456789")
PUNCTUATION = set(".,")
VOWEL_ORDER = "aeiou"
CONSONANT_ORDER = "tnshrdlucmfwypvbgkqjxz"

# Default text for testing
DEFAULT_TEXT = "....... Ahhhhhhhhhhhhhhh 1234567890, What is this? What is this? It is text2midi 1234567890 WOW WOW ..nice.. Make the make the music make the music with no skill. Out now. Out now. TTTTHHHHXXXX. Welcome to text-2-midi ACID music converter. Yeeeeeeeeeeeeeessssssssssssshh .. 1234567890 Lets get lets get lets get the party going. 1230 1234560 ACID music is the shit. Peace out."

# Timing constants
BPM = 130
TICKS_PER_BEAT = 4
TICK_DURATION = 60.0 / BPM / TICKS_PER_BEAT

# MIDI constants
NOTE_BASE = 48  # C3 for TB-303 basslines
OCTAVE = 12
MINOR_PENTATONIC = [0, 3, 5, 7, 10]  # C, Eb, F, G, Bb
PAD_CHORD_NOTES = [0, 3, 7]  # Root, minor 3rd, 5th for ambient chords
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
    'TB303': ('TextMIDI_TB303', 'virtual-1'),
    'BP909': ('TextMIDI_BP909', 'virtual-2'),
    'LeadSynth': ('TextMIDI_LeadSynth', 'virtual-3'),
    'PadSynth': ('TextMIDI_PadSynth', 'virtual-4')
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
    random.seed(text)  # Deterministic mapping for decodability
    event_queue = []
    char_timing = []
    current_time = 0

    for i, ch in enumerate(text):
        ch_lower = ch.lower()

        if ch == ' ' or ch_lower in PUNCTUATION:
            char_timing.append((current_time, i, ch))
            # TB303: Resonance tweak
            heapq.heappush(event_queue, (current_time, 'TB303', 'cc', 71, 60))
            # PadSynth: Sustained minor chord
            chord_root = NOTE_BASE + MINOR_PENTATONIC[0] + OCTAVE  # One octave above bassline
            for offset in PAD_CHORD_NOTES:
                note = chord_root + offset
                note = min(max(note, 0), 127)
                heapq.heappush(event_queue, (current_time, 'PadSynth', 'on', note, 60))
                heapq.heappush(event_queue, (current_time + 4, 'PadSynth', 'off', note, 0))
            current_time += 1
            continue

        if ch_lower not in ENCODABLE:
            char_timing.append((current_time, i, ch))
            continue

        # Bassline (TB303 device)
        if ch_lower in VOWELS:
            rank = VOWEL_ORDER.index(ch_lower)
            scale_degree = MINOR_PENTATONIC[rank % len(MINOR_PENTATONIC)]
            note = NOTE_BASE + scale_degree
            note = min(max(note, 0), 127)
            velocity = 80
            duration = 2 if random.random() < 0.6 else 1
            heapq.heappush(event_queue, (current_time, 'TB303', 'on', note, velocity))
            heapq.heappush(event_queue, (current_time + duration, 'TB303', 'off', note, 0))
            if duration > 1:
                heapq.heappush(event_queue, (current_time, 'TB303', 'cc', 5, 127))
                heapq.heappush(event_queue, (current_time + duration, 'TB303', 'cc', 5, 0))
        elif ch_lower in DIGITS:
            rank = int(ch_lower)
            scale_degree = MINOR_PENTATONIC[rank % len(MINOR_PENTATONIC)]
            note = NOTE_BASE + scale_degree
            note = min(max(note, 0), 127)
            velocity = 70
            heapq.heappush(event_queue, (current_time, 'TB303', 'on', note, velocity))
            heapq.heappush(event_queue, (current_time + 1, 'TB303', 'off', note, 0))
        elif ch_lower in CONSONANT_ORDER:
            rank = CONSONANT_ORDER.index(ch_lower)
            scale_degree = MINOR_PENTATONIC[rank % len(MINOR_PENTATONIC)]
            note = NOTE_BASE + scale_degree
            note = min(max(note, 0), 127)
            velocity = 100
            heapq.heappush(event_queue, (current_time, 'TB303', 'on', note, velocity))
            heapq.heappush(event_queue, (current_time + 1, 'TB303', 'off', note, 0))
            heapq.heappush(event_queue, (current_time, 'TB303', 'cc', 71, 80))

        # Drums (BP909 device)
        if ch_lower in VOWELS:
            heapq.heappush(event_queue, (current_time, 'BP909', 'on', DRUM_NOTES['kick'], 100))
            heapq.heappush(event_queue, (current_time + 1, 'BP909', 'off', DRUM_NOTES['kick'], 0))
        elif ch_lower in DIGITS:
            heapq.heappush(event_queue, (current_time, 'BP909', 'on', DRUM_NOTES['oh'], 80))
            heapq.heappush(event_queue, (current_time + 1, 'BP909', 'off', DRUM_NOTES['oh'], 0))
        elif ch_lower in CONSONANT_ORDER:
            drum = 'snare' if (i % 4 == 2) else 'clap' if (i % 4 == 0) else 'ch'
            velocity = 90 if drum in ['snare', 'clap'] else 70
            heapq.heappush(event_queue, (current_time, 'BP909', 'on', DRUM_NOTES[drum], velocity))
            heapq.heappush(event_queue, (current_time + 1, 'BP909', 'off', DRUM_NOTES[drum], 0))

        char_timing.append((current_time, i, ch))
        current_time += 1

    return sorted(event_queue), sorted(char_timing, key=lambda x: x[1])

def play_event_queue(midiouts, event_queue, char_queue):
    active_notes = {device: set() for device in DEVICES}
    try:
        events = [(e[0], e[1], e[2], e[3], e[4] if len(e) > 4 else 0) for e in event_queue]
        events.sort(key=lambda x: x[0])

        char_ready_ticks = {i: tick for tick, i, _ in char_queue}
        text_order = [ch for _, _, ch in char_queue]

        event_ptr = 0
        tick = 0
        max_tick = max([e[0] for e in events] + list(char_ready_ticks.values()), default=0) + 1

        while tick <= max_tick:
            if char_queue and char_ready_ticks.get(len(text_order) - len(char_queue)) <= tick:
                _, _, ch = char_queue.pop(0)
                print(ch, end='', flush=True)

            while event_ptr < len(events) and events[event_ptr][0] == tick:
                _, device, action, value, param = events[event_ptr]
                midiout = midiouts[device]
                if action == 'on':
                    midiout.send_message([0x90, value, param])
                    active_notes[device].add(value)
                elif action == 'off':
                    midiout.send_message([0x80, value, 0])
                    active_notes[device].discard(value)
                elif action == 'cc':
                    midiout.send_message([0xB0, value, param])
                event_ptr += 1

            time.sleep(TICK_DURATION)
            tick += 1

    finally:
        for device, notes in active_notes.items():
            midiout = midiouts[device]
            for note in notes:
                midiout.send_message([0x80, note, 0])
        print("\nAll notes off.")

def main():
    text = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else DEFAULT_TEXT
    text = text + " "

    midiouts = {}
    try:
        for device, (src_port, _) in DEVICES.items():
            midiout = rtmidi.MidiOut(rtapi=rtmidi.API_LINUX_ALSA)
            midiout.open_virtual_port(src_port)
            midiouts[device] = midiout
    except Exception:
        print("Failed to open MIDI ports")
        return

    time.sleep(0.5)  # Delay for port availability
    for device, (src_port, dst_port) in DEVICES.items():
        if not connect_midi_ports(src_port, dst_port):
            print(f"Failed to connect {src_port} to {dst_port}; continuing...")

    print(f"Encoding and playing ACID pattern ({len(text)} characters)...\n")
    event_queue, char_queue = text_to_event_queue(text)
    play_event_queue(midiouts, event_queue, char_queue)

if __name__ == "__main__":
    main()
