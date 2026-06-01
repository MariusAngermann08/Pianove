import pygame as pg
import sys
import mido

# Filter out virtual "Midi Through" ports on Linux
def get_physical_inputs():
    try:
        return [name for name in mido.get_input_names() if "Midi Through" not in name]
    except Exception as e:
        print(f"Error listing MIDI devices: {e}")
        return []

devices = get_physical_inputs()
midi_in = None
if devices:
    try:
        midi_in = mido.open_input(devices[0])
        print(f"Connected to MIDI device: {midi_in.name}")
    except Exception as e:
        print(f"Error opening MIDI device: {e}")

pg.init()

font = pg.font.SysFont(None, 60)
screen = pg.display.set_mode((1000,500))
pg.display.set_caption("Midi Tester")
clock = pg.time.Clock()

class Piano:
    whitekeywidth = int(round((1000-30)/15))
    whitekeyheight = 300
    blackkeywidth = int(round((1000-30)/15/2))
    blackkeyheight = 200
    def __init__(self, surface=None):
        self.white_keys = []
        self.black_keys = []
        self.surface = surface
    def build(self, active_notes=None):
        if active_notes is None:
            active_notes = set()
        self.white_keys.clear()
        self.black_keys.clear()
        
        start_note = 48  # C3
        
        def is_note_active(note_num):
            if note_num in active_notes:
                return True
            for active_note in active_notes:
                if active_note < 48 or active_note > 72:
                    if (active_note - 48) % 12 == (note_num - 48) % 12:
                        return True
            return False

        # C3 to C5 white keys
        white_key_notes = [48, 50, 52, 53, 55, 57, 59, 60, 62, 64, 65, 67, 69, 71, 72]
        for i, note in enumerate(white_key_notes):
            key = (int(round(15+i*self.whitekeywidth)),40,int(round(self.whitekeywidth)),self.whitekeyheight)
            color = (190, 60, 60) if is_note_active(note) else (255,255,255)
            self.white_keys.append([key, color])

        # C3 to C5 black keys
        black_key_notes = [49, 51, 54, 56, 58, 61, 63, 66, 68, 70]
        black_key_indices = [0,1,3,4,5,7,8,10,11,12]  # C#, D#, F#, G#, A#, etc.
        for idx, note in zip(black_key_indices, black_key_notes):
            left_white_x = int(round(15 + idx * self.whitekeywidth))
            x = left_white_x + self.whitekeywidth - self.blackkeywidth // 2
            key = (x, 40, int(round(self.blackkeywidth)), self.blackkeyheight)
            color = (140, 45, 45) if is_note_active(note) else (0,0,0)
            self.black_keys.append([key, color])
            
    def draw(self, active_notes=None):
        if self.surface:
            self.build(active_notes)
            for key in self.white_keys:
                pg.draw.rect(self.surface,key[1],key[0],0,0)
                pg.draw.rect(self.surface,(0,0,0),key[0],2,0)
            for key in self.black_keys:
                pg.draw.rect(self.surface,key[1],key[0],0,10)
                pg.draw.rect(self.surface,(0,0,0),key[0],2,10)



piano = Piano(surface=screen)
piano.build()
print(piano.white_keys)

active_notes = set()
last_midi_check = 0

while True:
    for event in pg.event.get():
        if event.type == pg.QUIT:
            if midi_in:
                try:
                    midi_in.close()
                except Exception:
                    pass
            pg.quit()
            sys.exit()
    

    # Check MIDI connection every 1 second (1000 ms) to avoid high CPU/IO load
    current_time = pg.time.get_ticks()
    if current_time - last_midi_check > 1000:
        last_midi_check = current_time
        devices = get_physical_inputs()
        if midi_in is None:
            if devices:
                try:
                    midi_in = mido.open_input(devices[0])
                    print(f"Connected to MIDI device: {midi_in.name}")
                except Exception as e:
                    print(f"Error opening MIDI device: {e}")
        else:
            if midi_in.name not in mido.get_input_names():
                print(f"Disconnected from MIDI device: {midi_in.name}")
                try:
                    midi_in.close()
                except Exception:
                    pass
                midi_in = None
                active_notes.clear()

    midi_connected = midi_in is not None
    label_text = "MIDI Connected" if midi_connected else "No MIDI Device"
    label_color = (0, 128, 0) if midi_connected else (200, 0, 0)
    label = font.render(label_text, True, label_color)

    # Fetch MIDI messages:
    if midi_in:
        try:
            for msg in midi_in.iter_pending():
                print(msg)
                if msg.type == 'note_on':
                    if msg.velocity > 0:
                        active_notes.add(msg.note)
                    else:
                        active_notes.discard(msg.note)
                elif msg.type == 'note_off':
                    active_notes.discard(msg.note)
        except Exception as e:
            print(f"Error reading MIDI messages: {e}")
            try:
                midi_in.close()
            except Exception:
                pass
            midi_in = None
            active_notes.clear()
    
    screen.fill((255,255,255))

    #Draw Stuff
    piano.draw(active_notes)
    screen.blit(label, (20,400))

    pg.display.update()
    clock.tick(60)