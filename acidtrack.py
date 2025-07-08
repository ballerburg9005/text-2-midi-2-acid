#!/usr/bin/env python3
import time
import subprocess
import re
import rtmidi
import heapq
import random

# Timing constants
BPM = 135  # Increased for faster feel
TICKS_PER_BEAT = 4
TICK_DURATION = 60.0 / BPM / TICKS_PER_BEAT
BARS = 32
BEATS_PER_BAR = 4
TOTAL_TICKS = BARS * BEATS_PER_BAR * TICKS_PER_BEAT  # 512 ticks

# ATTENTION AI: IN FL STUDIO C-4 IS 48!!!! NOT 50!!!!

# MIDI constants
NOTE_BASE = 36  # C3 for basslines
OCTAVE = 12
MINOR_PENTATONIC = [0, 3, 5, 7, 10]  # C, Eb, F, G, Bb
PAD_CHORD_NOTES = [0, 3, 7]  # Root, minor 3rd, 5th

# DONT FUCKING CHANGE THIS, IT IS THE CORRECT MAPPING IN VST
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
SAMPLE_NOTES = {
    'vocal1': 48,  # C4 ("acid!")
    'vocal2': 50,  # D4 ("get down!")
    'riser': 52,   # E4 (riser FX)
    'sweep': 53    # F4 (sweep FX)
}

# Device mapping to ALSA ports and MIDI channels
DEVICES = {
    'TB303': ('AcidTrack_TB303', 'virtual-1', 1),        # Bassline, channel 1
    'BP909': ('AcidTrack_BP909', 'virtual-2', 2),        # Drums, channel 2
    'LeadSynth': ('AcidTrack_LeadSynth', 'virtual-3', 3), # Lead melody, channel 3
    'PadSynth': ('AcidTrack_PadSynth', 'virtual-4', 4),  # Pads, channel 4
    'SampleBank1': ('AcidTrack_Sample1', 'virtual-5', 5), # Vocal chops, channel 5
    'SampleBank2': ('AcidTrack_Sample2', 'virtual-6', 6), # FX, channel 6
    'ArpSynth': ('AcidTrack_ArpSynth', 'virtual-7', 7),  # Arpeggiator, channel 7
    'BassSub': ('AcidTrack_BassSub', 'virtual-8', 8)     # Sub-bass, channel 8
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

def generate_acid_patterns():
    """Generate ACID track patterns for 32 bars (512 ticks)"""
    random.seed(42)  # Consistent patterns
    event_queue = []

    # TB303: Acid bassline with overlapping slides and dynamic CCs
    for bar in range(BARS):
        start_tick = bar * BEATS_PER_BAR * TICKS_PER_BEAT
        pattern = [0, 3, 5, 0, 7, 10, 3, 5] if bar % 2 == 0 else [0, 5, 10, 0, 3, 7, 5, 3]
        for i in range(8):
            tick = start_tick + i * 2
            if random.random() < 0.95:  # High note density
                note = NOTE_BASE + MINOR_PENTATONIC[pattern[i] % len(MINOR_PENTATONIC)]
                note = min(max(note, 0), 127)
                velocity = 90 + random.randint(-10, 10)
                duration = 3 if random.random() < 0.7 else 2  # Longer for slides
                heapq.heappush(event_queue, (tick, 'TB303', 'on', note, velocity))
                heapq.heappush(event_queue, (tick + duration, 'TB303', 'off', note, 0))
                # Overlapping slides
                heapq.heappush(event_queue, (tick, 'TB303', 'cc', 5, 127 if random.random() < 0.8 else 0))  # 80% slide chance
                heapq.heappush(event_queue, (tick + duration, 'TB303', 'cc', 5, 0))
                # Dynamic resonance and cutoff
                heapq.heappush(event_queue, (tick, 'TB303', 'cc', 71, 80 + random.randint(0, 40)))
                heapq.heappush(event_queue, (tick, 'TB303', 'cc', 74, 60 + random.randint(0, 50)))

    # BassSub: Deep sub-bass
    for bar in range(BARS):
        start_tick = bar * BEATS_PER_BAR * TICKS_PER_BEAT
        if bar >= 2:
            for beat in range(4):
                tick = start_tick + beat * TICKS_PER_BEAT
                note = NOTE_BASE - OCTAVE  # C2
                heapq.heappush(event_queue, (tick, 'BassSub', 'on', note, 100))
                heapq.heappush(event_queue, (tick + 2, 'BassSub', 'off', note, 0))

    # BP909: Dense drum pattern with variation
    for bar in range(BARS):
        start_tick = bar * BEATS_PER_BAR * TICKS_PER_BEAT
        for beat in range(4):
            tick = start_tick + beat * TICKS_PER_BEAT
            # Kick on every beat, with occasional offbeat
            heapq.heappush(event_queue, (tick, 'BP909', 'on', DRUM_NOTES['kick'], 100))
            heapq.heappush(event_queue, (tick + 1, 'BP909', 'off', DRUM_NOTES['kick'], 0))
            if random.random() < 0.2 and beat % 2 == 1:
                heapq.heappush(event_queue, (tick + 2, 'BP909', 'on', DRUM_NOTES['kick'], 80))
                heapq.heappush(event_queue, (tick + 3, 'BP909', 'off', DRUM_NOTES['kick'], 0))
            # Snare on 2 and 4
            if beat % 2 == 1:
                heapq.heappush(event_queue, (tick, 'BP909', 'on', DRUM_NOTES['snare'], 90))
                heapq.heappush(event_queue, (tick + 1, 'BP909', 'off', DRUM_NOTES['snare'], 0))
            # Clap on offbeats
            if beat % 2 == 1 and bar >= 4:
                heapq.heappush(event_queue, (tick + 2, 'BP909', 'on', DRUM_NOTES['clap'], 85))
                heapq.heappush(event_queue, (tick + 3, 'BP909', 'off', DRUM_NOTES['clap'], 0))
            # 16th-note closed hi-hats
            for i in range(4):
                htick = tick + i
                heapq.heappush(event_queue, (htick, 'BP909', 'on', DRUM_NOTES['ch'], 70 + random.randint(-10, 10)))
                heapq.heappush(event_queue, (htick + 1, 'BP909', 'off', DRUM_NOTES['ch'], 0))
            # Open hi-hat on offbeats
            if beat % 2 == 1:
                heapq.heappush(event_queue, (tick + 2, 'BP909', 'on', DRUM_NOTES['oh'], 80))
                heapq.heappush(event_queue, (tick + 3, 'BP909', 'off', DRUM_NOTES['oh'], 0))
            # Toms and rimshots for variation
            if bar >= 8 and random.random() < 0.3:
                tom = 'ltom' if random.random() < 0.5 else 'htom'
                heapq.heappush(event_queue, (tick + 3, 'BP909', 'on', DRUM_NOTES[tom], 80))
                heapq.heappush(event_queue, (tick + 4, 'BP909', 'off', DRUM_NOTES[tom], 0))
            if bar >= 12 and random.random() < 0.2:
                heapq.heappush(event_queue, (tick + 1, 'BP909', 'on', DRUM_NOTES['rim'], 75))
                heapq.heappush(event_queue, (tick + 2, 'BP909', 'off', DRUM_NOTES['rim'], 0))
            # Crash every 4 bars
            if beat == 0 and bar % 4 == 0:
                heapq.heappush(event_queue, (tick, 'BP909', 'on', DRUM_NOTES['crash'], 90))
                heapq.heappush(event_queue, (tick + 2, 'BP909', 'off', DRUM_NOTES['crash'], 0))

    # LeadSynth: Melodic stabs
    for bar in range(4, BARS):
        start_tick = bar * BEATS_PER_BAR * TICKS_PER_BEAT
        for beat in [0, 2]:
            tick = start_tick + beat * TICKS_PER_BEAT
            note = NOTE_BASE + OCTAVE + MINOR_PENTATONIC[random.randint(0, 4)]
            note = min(max(note, 0), 127)
            heapq.heappush(event_queue, (tick, 'LeadSynth', 'on', note, 80))
            heapq.heappush(event_queue, (tick + 2, 'LeadSynth', 'off', note, 0))

    # ArpSynth: Arpeggiated pattern
    for bar in range(8, BARS):
        start_tick = bar * BEATS_PER_BAR * TICKS_PER_BEAT
        arp_notes = [0, 3, 7, 10, 7, 3]
        for i in range(8):
            tick = start_tick + i * 2
            note = NOTE_BASE + OCTAVE * 2 + MINOR_PENTATONIC[arp_notes[i % len(arp_notes)] % len(MINOR_PENTATONIC)]
            note = min(max(note, 0), 127)
            heapq.heappush(event_queue, (tick, 'ArpSynth', 'on', note, 75))
            heapq.heappush(event_queue, (tick + 1, 'ArpSynth', 'off', note, 0))

    # PadSynth: Ambient chords
    for bar in range(2, 28):
        start_tick = bar * BEATS_PER_BAR * TICKS_PER_BEAT
        chord_root = NOTE_BASE + OCTAVE + MINOR_PENTATONIC[0]
        for offset in PAD_CHORD_NOTES:
            note = chord_root + offset
            note = min(max(note, 0), 127)
            heapq.heappush(event_queue, (start_tick, 'PadSynth', 'on', note, 60))
            heapq.heappush(event_queue, (start_tick + 16, 'PadSynth', 'off', note, 0))

    # SampleBank1: Vocal chops
    for bar in range(4, BARS, 4):
        start_tick = bar * BEATS_PER_BAR * TICKS_PER_BEAT
        heapq.heappush(event_queue, (start_tick, 'SampleBank1', 'on', SAMPLE_NOTES['vocal1'], 100))
        heapq.heappush(event_queue, (start_tick + 4, 'SampleBank1', 'off', SAMPLE_NOTES['vocal1'], 0))
        if bar >= 12:
            heapq.heappush(event_queue, (start_tick + 8, 'SampleBank1', 'on', SAMPLE_NOTES['vocal2'], 100))
            heapq.heappush(event_queue, (start_tick + 12, 'SampleBank1', 'off', SAMPLE_NOTES['vocal2'], 0))

    # SampleBank2: FX (riser in breakdown)
    for bar in range(20, 24):
        start_tick = bar * BEATS_PER_BAR * TICKS_PER_BEAT
        heapq.heappush(event_queue, (start_tick, 'SampleBank2', 'on', SAMPLE_NOTES['riser'], 90))
        heapq.heappush(event_queue, (start_tick + 16, 'SampleBank2', 'off', SAMPLE_NOTES['riser'], 0))

    return sorted(event_queue)

def play_event_queue(midiouts, event_queue):
    active_notes = {device: set() for device in DEVICES}
    try:
        events = [(e[0], e[1], e[2], e[3], e[4] if len(e) > 4 else 0) for e in event_queue]
        events.sort(key=lambda x: x[0])

        event_ptr = 0
        tick = 0
        max_tick = max([e[0] for e in events], default=0) + 1

        while tick <= max_tick:
            while event_ptr < len(events) and events[event_ptr][0] == tick:
                _, device, action, value, param = events[event_ptr]
                channel = DEVICES[device][2] - 1  # MIDI channels 0-15
                midiout = midiouts[device]
                if action == 'on':
                    midiout.send_message([0x90 | channel, value, param])
                    active_notes[device].add(value)
#                    print(f"Sending {device} note on: {value} (channel {channel + 1}) at tick {tick}")
                elif action == 'off':
                    midiout.send_message([0x80 | channel, value, 0])
                    active_notes[device].discard(value)
#                    print(f"Sending {device} note off: {value} (channel {channel + 1}) at tick {tick}")
                elif action == 'cc':
                    midiout.send_message([0xB0 | channel, value, param])
#                    print(f"Sending {device} CC {value}: {param} (channel {channel + 1}) at tick {tick}")
                event_ptr += 1

            time.sleep(TICK_DURATION)
            tick += 1

    finally:
        for device, notes in active_notes.items():
            channel = DEVICES[device][2] - 1
            midiout = midiouts[device]
            for note in notes:
                midiout.send_message([0x80 | channel, note, 0])
        print("\nAll notes off.")

def main():
    midiouts = {}
    try:
        for device, (src_port, _, _) in DEVICES.items():
            midiout = rtmidi.MidiOut(rtapi=rtmidi.API_LINUX_ALSA)
            midiout.open_virtual_port(src_port)
            midiouts[device] = midiout
    except Exception:
        print("Failed to open MIDI ports")
        return

    time.sleep(0.5)  # Increased for reliable ALSA connections
    for device, (src_port, dst_port, _) in DEVICES.items():
        if not connect_midi_ports(src_port, dst_port):
            print(f"Failed to connect {src_port} to {dst_port}; continuing...")

    print(f"Generating and playing ACID track ({BARS} bars)...\n")
    event_queue = generate_acid_patterns()
    play_event_queue(midiouts, event_queue)

if __name__ == "__main__":
    main()
