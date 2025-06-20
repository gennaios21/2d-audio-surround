import tkinter as tk
from tkinter import filedialog
import sounddevice as sd
import soundfile as sf
import numpy as np
import math

# ---------------------- Your existing audio variables ------------------------

audio_data = None
fs = 44100
pointer = 0
playing = False
stream = None
volume = 1.0
last_azimuth = 0                  
current_playing = None
slider_updating = False
vbap_gain = np.array([1.0]*5)        
force_stereo = False               # True for 2.0, false for 5.0
control_buttons = {}   
music_slider = None

# Azimuth angles per speaker
speaker_angles_deg = {
    "Center": 0,
    "Right": 30,
    "Rear Right": 110,
    "Rear Left": -110,
    "Left": -30
}

# ---------------------- Audio and Playback functions ------------------------

def load_file():
    global audio_data, fs, pointer, stream
    path = filedialog.askopenfilename(filetypes=[("WAV files", "*.wav")])
    if path:
        data, fs = sf.read(path, dtype='float32')
        if data.ndim == 1:
            data = data[:, np.newaxis]
        audio_data = data
        pointer = 0
        status_label.config(text=f"Loaded: {path.split('/')[-1]}", fg='red')
        music_slider.config(to=int(len(audio_data) / fs))
        duration_label_static.config(text=format_time(len(audio_data) / fs))
        duration_label_dynamic.config(text=format_time(len(audio_data) / fs))
        if not stream:
            start_stream()

def start_stream():
    global stream
    channels = 2 if force_stereo else 5
    stream = sd.OutputStream(
        samplerate=fs,
        channels=channels,
        callback=audio_callback
    )
    stream.start()

def audio_callback(outdata, frames, time, status):
    global pointer, playing, volume, vbap_gain

    if not playing or audio_data is None:
        outdata[:] = np.zeros_like(outdata)
        return

    end = pointer + frames
    chunk = audio_data[pointer:end]

    if len(chunk) < frames:
        chunk = np.concatenate([chunk, np.zeros((frames - len(chunk), audio_data.shape[1]))])
        playing = False
        ui_choice.get() == "static" and update_all_buttons()

    mono_chunk = chunk[:, 0] if chunk.shape[1] == 1 else chunk[:, 0]

    if outdata.shape[1] == 5:
        output = np.zeros((frames, 5))
        for i in range(5):
            output[:, i] = mono_chunk * vbap_gain[i] * volume
        outdata[:] = output

    elif outdata.shape[1] == 2:
        stereo_output = np.zeros((frames, 2))
        stereo_output[:, 0] = mono_chunk * (vbap_gain[0] + 0.7 * vbap_gain[2] + vbap_gain[3]) * volume
        stereo_output[:, 1] = mono_chunk * (vbap_gain[1] + 0.7 * vbap_gain[2] + vbap_gain[4]) * volume
        outdata[:] = stereo_output

    pointer += frames

# Dynamic playback
def start_playback(azimuth):
    global playing, pointer, stream, vbap_gain, last_azimuth
    if audio_data is None:
        print("No file loaded!")
        return

    if azimuth is not None:
        last_azimuth = azimuth

    if pointer >= len(audio_data):
        pointer = 0
    if stream:
        stream.stop()
    playing = True
    vbap_gain = calculate_vbap_gain(last_azimuth)
    start_stream()
    update_play_button()

def toggle_playback():
    global playing, current_playing, last_azimuth

    if audio_data is None:
        status_label.config(text="Load a .wav file first!", fg="red")
        return
    if playing:
        stop_playback()
    else:
        start_playback(current_playing if current_playing else last_azimuth)

def stop_playback():
    global playing
    playing = False
    update_play_button()

def update_play_button():
    play_stop_button.config(
        text="Stop" if playing else "Play", 
        bg="red" if playing else "green"
    )


# Static playback
def toggle_playback_static(speaker_name):
    global playing, pointer, current_playing

    if audio_data is None:
        return

    if current_playing and current_playing != speaker_name:
        stop_playback_static(current_playing)

    if playing and current_playing == speaker_name:
        stop_playback_static(speaker_name)
    else:
        start_playback_static(speaker_name)

def start_playback_static(speaker_name):
    global playing, pointer, current_playing, stream, vbap_gain
    if pointer >= len(audio_data):
        pointer = 0
    if stream:
        stream.stop()
    playing = True
    current_playing = speaker_name
    update_button(speaker_name)
    azimuth = speaker_angles_deg[speaker_name]
    vbap_gain = calculate_vbap_gain(azimuth)
    start_stream()

def stop_playback_static(speaker_name):
    global playing, current_playing, stream
    playing = False
    current_playing = None
    if stream:
        stream.stop()
    update_button(speaker_name)

# ---------------------- VBAP Gain Calculation ------------------------

def normalize(v):
    norm = np.linalg.norm(v)
    return v / norm if norm > 0 else v

def calculate_vbap_gain(source_angle_deg):
    speaker_angles = [-30, 30, 0, -110, 110]
    speaker_pairs = [
        (0, 2), (1, 2), (0, 3), (1, 4), (3, 4)
    ]

    source_angle_rad = np.radians(source_angle_deg)
    source_vec = np.array([np.cos(source_angle_rad), np.sin(source_angle_rad)])

    best_gains = np.zeros(5)
    for i, j in speaker_pairs:
        v1 = np.array([np.cos(np.radians(speaker_angles[i])), np.sin(np.radians(speaker_angles[i]))])
        v2 = np.array([np.cos(np.radians(speaker_angles[j])), np.sin(np.radians(speaker_angles[j]))])
        L = np.column_stack((v1, v2))
        try:
            L_inv = np.linalg.inv(L)
        except np.linalg.LinAlgError:
            continue
        gains_pair = np.dot(L_inv, source_vec)
        if np.all(gains_pair >= 0):
            gains_pair = normalize(gains_pair)
            gains_full = np.zeros(len(speaker_angles))
            gains_full[i] = gains_pair[0]
            gains_full[j] = gains_pair[1]
            best_gains = gains_full
            break
    return best_gains

def update_vbap_for_angle(angle):
    global vbap_gain
    vbap_gain = calculate_vbap_gain(angle)

# ---------------------- Dyanmic GUI Update Helpers ------------------------

def on_volume_change(val):
    global volume
    volume = float(val) / 100.0

def on_music_slider_change(val):
    global pointer, slider_updating
    if slider_updating:
        return
    if audio_data is not None:
        pointer = int(float(val)) * fs

def update_music_slider():
    global slider_updating
    if audio_data is not None and playing:
        slider_updating = True
        seconds = pointer / fs
        music_slider.set(int(seconds))
        current_time_label_static.config(text=format_time(seconds))
        current_time_label_dynamic.config(text=format_time(seconds))
        slider_updating = False
    root.after(200, update_music_slider)

def format_time(seconds):
    m = int(seconds) // 60
    s = int(seconds) % 60
    return f"{m:02d}:{s:02d}"


# ======================== Static GUI Update Helpers ========================
def update_button(speaker_name):
    if speaker_name == current_playing:
        control_buttons[speaker_name].config(
            text=f"{speaker_name} Playing ({speaker_angles_deg[speaker_name]}°)", bg="red"
        )
    else:
        control_buttons[speaker_name].config(
            text=f"{speaker_name} ({speaker_angles_deg[speaker_name]}°)", bg="green"
        )

def update_all_buttons():
    for speaker_name in control_buttons:
        update_button(speaker_name)



# ---------------------- CircularSlider class ------------------------

class CircularSlider(tk.Canvas):
    def __init__(self, parent, radius=140, padding=70, **kwargs):
        self.radius = radius
        self.padding = padding
        total_size = 2 * radius + padding

        kwargs.pop('width', None)
        kwargs.pop('height', None)

        super().__init__(parent, width=total_size, height=total_size, **kwargs)

        self.center = (radius + padding // 2, radius + padding // 2)
        self.angle = 0
        self.bind("<Enter>", self.on_enter)
        self.bind("<Leave>", self.on_leave)
        self.bind("<B1-Motion>", self.on_drag)
        self.bind("<ButtonRelease-1>", self.on_release)
        self.draw_slider()

    def draw_slider(self):
        self.delete("all")
        x0 = self.center[0] - self.radius
        y0 = self.center[1] - self.radius
        x1 = self.center[0] + self.radius
        y1 = self.center[1] + self.radius
        # Circle
        self.create_oval(x0, y0, x1, y1, outline="black", width=3)
        
        # Line for angle
        x = self.center[0] + self.radius * math.cos(math.radians(self.angle - 90))
        y = self.center[1] + self.radius * math.sin(math.radians(self.angle - 90))
        self.create_line(self.center[0], self.center[1], x, y, width=3, fill="red")

        # Degree markers
        for deg in [90, 180, 270]:
            rad = math.radians(deg - 90)
            x_m = self.center[0] + (self.radius + 15) * math.cos(rad)
            y_m = self.center[1] + (self.radius + 15) * math.sin(rad)
            self.create_text(x_m, y_m, text=str(deg)+"°", font=("Arial", 14))
        
        # Speaker markers
        for deg in [0, 30, 110, 250, 330]:
            rad = math.radians(deg - 90)
            x_m = self.center[0] + (self.radius + 15) * math.cos(rad)
            y_m = self.center[1] + (self.radius + 15) * math.sin(rad)
            self.create_text(x_m, y_m, text="🔊"+str(deg)+"°", fill='blue', font=("Arial", 14))

    def on_enter(self, event):
        self.config(cursor="hand2")

    def on_leave(self, event):
        self.config(cursor="")

    def on_drag(self, event):
        dx = event.x - self.center[0]
        dy = event.y - self.center[1]
        self.angle = (math.degrees(math.atan2(dy, dx)) + 90) % 360  
        self.draw_slider()
        update_vbap_for_angle(self.angle) 
        

    def on_release(self, event):
        dx = event.x - self.center[0]
        dy = event.y - self.center[1]
        self.angle = (math.degrees(math.atan2(dy, dx)) + 90) % 360
        self.draw_slider()

        global last_azimuth
        last_azimuth = self.angle
        start_playback(self.angle)

# ---------------------- Main window ------------------------

root = tk.Tk()
root.title("5.0 Surround Audio Player with VBAP")
root.geometry("1200x750")

# --- Radio button variable and switch function ---

ui_choice = tk.StringVar(value="static")

def switch_ui():
    if ui_choice.get() == "static":
        dynamic_frame.pack_forget()
        static_frame.pack(fill="both", expand=True)
    else:
        static_frame.pack_forget()
        dynamic_frame.pack(fill="both", expand=True)

# --- Radio buttons for UI selection ---

radio_frame = tk.Frame(root)
radio_frame.pack(pady=5)
tk.Label(radio_frame, text="Select UI: ", font=("Arial", 14)).pack(side=tk.LEFT)
tk.Radiobutton(radio_frame, text="Static", variable=ui_choice, value="static", command=switch_ui, font=("Arial", 14)).pack(side=tk.LEFT)
tk.Radiobutton(radio_frame, text="Dynamic", variable=ui_choice, value="dynamic", command=switch_ui, font=("Arial", 14)).pack(side=tk.LEFT)

# Load button
load_btn = tk.Button(root, text="Load File (.wav)", bg="lightblue", command=load_file, font=("Arial", 14), cursor="hand2")
load_btn.pack(pady=10)

status_label = tk.Label(root, text="No file loaded", foreground='red', font=("Arial", 14))
status_label.pack()

# --- STATIC UI ---

static_frame = tk.Frame(root)
static_frame.pack(fill="both", expand=True)

layout = tk.Frame(static_frame)
layout.pack(pady=20)

grid_layout = tk.Frame(layout)
grid_layout.grid(row=0, column=0, pady=10)

btn_c = tk.Button(grid_layout, text="Center (0°) 🔊", width=20, height=2, font=("Arial", 14), bg="green", command=lambda: toggle_playback_static("Center"), cursor="hand2")
btn_c.grid(row=0, column=1, padx=20, pady=20)

btn_l = tk.Button(grid_layout, text="Left (-30°) 🔊", width=15, height=2, font=("Arial", 14), bg="green", command=lambda: toggle_playback_static("Left"), cursor="hand2")
btn_l.grid(row=1, column=0, padx=20, pady=20)

btn_r = tk.Button(grid_layout, text="Right (30°) 🔊", width=15, height=2, font=("Arial", 14), bg="green", command=lambda: toggle_playback_static("Right"), cursor="hand2")
btn_r.grid(row=1, column=2, padx=20, pady=20)

btn_rl = tk.Button(grid_layout, text="Rear Left (-110°) 🔊", width=20, height=2, font=("Arial", 14), bg="green", command=lambda: toggle_playback_static("Rear Left"), cursor="hand2")
btn_rl.grid(row=2, column=0, padx=20, pady=20)

btn_rr = tk.Button(grid_layout, text="Rear Right (110°) 🔊", width=20, height=2, font=("Arial", 14), bg="green", command=lambda: toggle_playback_static("Rear Right"), cursor="hand2")
btn_rr.grid(row=2, column=2, padx=20, pady=20)

control_buttons["Center"] = btn_c
control_buttons["Left"] = btn_l
control_buttons["Right"] = btn_r
control_buttons["Rear Left"] = btn_rl
control_buttons["Rear Right"] = btn_rr

listener_label = tk.Label(layout, text="🧍", font=("Arial", 40))
listener_label.place(relx=0.5, rely=0.5, anchor="center")

slider_frame_main = tk.Frame(static_frame)
slider_frame_main.pack(pady=10)

current_time_label_static = tk.Label(slider_frame_main, text="00:00", font=("Arial", 12))
current_time_label_static.pack(side=tk.LEFT)

music_slider = tk.Scale(
    slider_frame_main,
    from_=0,
    to=100,
    orient=tk.HORIZONTAL,
    length=500,
    showvalue=0,
    command=on_music_slider_change, 
    cursor="hand2"
)
music_slider.pack(side=tk.LEFT, padx=10)

duration_label_static = tk.Label(slider_frame_main, text="00:00", font=("Arial", 12))
duration_label_static.pack(side=tk.LEFT)

slider_frame = tk.Frame(static_frame)
slider_frame.pack(side=tk.RIGHT, padx=30, anchor="n")

tk.Label(slider_frame, text="Volume "+"🔊", font=("Arial", 16)).pack(pady=10)
volume_slider = tk.Scale(
    slider_frame,
    from_=100,
    to=0,
    orient=tk.VERTICAL,
    command=on_volume_change,
    length=300,
    font=("Arial", 12), 
    cursor="hand2"
)
volume_slider.set(50)
volume_slider.pack()

update_music_slider()

# --- DYNAMIC UI ---

dynamic_frame = tk.Frame(root)

layout = tk.Frame(dynamic_frame)
layout.pack(pady=20)

# Circular slider
slider = CircularSlider(dynamic_frame, radius=100, width=200, height=200)
slider.pack(pady=20)

# Play/Stop button
play_stop_button = tk.Button(dynamic_frame, text="Play", command=toggle_playback, bg="green", font=("Arial", 14), cursor="hand2")
play_stop_button.pack(pady=10)

# Music slider
slider_frame_main = tk.Frame(dynamic_frame)
slider_frame_main.pack(pady=10)

current_time_label_dynamic = tk.Label(slider_frame_main, text="00:00", font=("Arial", 12))
current_time_label_dynamic.pack(side=tk.LEFT)

music_slider = tk.Scale(
    slider_frame_main,
    from_=0,
    to=100,
    orient=tk.HORIZONTAL,
    length=500,
    showvalue=0,
    command=on_music_slider_change,
    cursor="hand2"
)
music_slider.pack(side=tk.LEFT, padx=10)

duration_label_dynamic = tk.Label(slider_frame_main, text="00:00", font=("Arial", 12))
duration_label_dynamic.pack(side=tk.LEFT)

# Volume slider
slider_frame = tk.Frame(dynamic_frame)
slider_frame.pack(side=tk.RIGHT, padx=30, anchor="n")

tk.Label(slider_frame, text="Volume "+"🔊", font=("Arial", 16)).pack(pady=10)
volume_slider = tk.Scale(
    slider_frame,
    from_=100,
    to=0,
    orient=tk.VERTICAL,
    command=on_volume_change,
    length=300,
    font=("Arial", 12),
    cursor="hand2"
)
volume_slider.set(50)
volume_slider.pack()

# Start slider update loop
update_music_slider()

# Find the audio hardware configuration of the computer's sound card
def callback(outdata, frames, time, status):
    outdata.fill(0)

with sd.OutputStream(callback=callback) as stream:
    device_info = sd.query_devices(stream.device)
    print(f"Using device: {device_info['name']} (Max Output Channels: {device_info['max_output_channels']})")
    # print(device_info)
    if device_info['max_output_channels'] == 2:
        force_stereo = True

print("Number of selected channels: ", 2.0 if force_stereo else 5.0)

root.mainloop()
