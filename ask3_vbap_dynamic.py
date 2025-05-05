import tkinter as tk
from tkinter import filedialog
import sounddevice as sd
import soundfile as sf
import numpy as np
import math


# ======================== Global audio state ========================

audio_data = None
fs = 44100
pointer = 0
playing = False
stream = None
volume = 1.0
last_azimuth = 0                  
current_playing = None
slider_updating = False
vbap_gain = np.array([1.0]*5)        # For 5 speakers
control_buttons = {}
music_slider = None
force_stereo = False               # True for 2.0, false for 5.0


# ======================== Audio and Playback ========================

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
        duration_label.config(text=format_time(len(audio_data) / fs))
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


# ======================== VBAP Gain Calculation ========================

def normalize(v):
    norm = np.linalg.norm(v)
    return v / norm if norm > 0 else v

def calculate_vbap_gain(source_angle_deg):
    speaker_angles = [-30, 30, 0, -110, 110]
    speaker_names = ["FL", "FR", "C", "RL", "RR"]
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
    # print(f"---- Selected azimuth/angle: {np.round(source_angle_deg, 2)}, Gains: {best_gains}, Selected speakers: {(speaker_angles[i], speaker_angles[j])}")
    return best_gains

def update_vbap_for_angle(angle):
    global vbap_gain
    vbap_gain = calculate_vbap_gain(angle)

# ======================== GUI Update Helpers ========================

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
        current_time_label.config(text=format_time(seconds))
        slider_updating = False
    root.after(200, update_music_slider)

def format_time(seconds):
    m = int(seconds) // 60
    s = int(seconds) % 60
    return f"{m:02d}:{s:02d}"

# ======================== GUI Setup ========================

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
        # Change cursor to a hand when mouse enters the circle
        self.config(cursor="hand2")

    def on_leave(self, event):
        # Revert the cursor back to default when mouse leaves the circle
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

# GUI Window
root = tk.Tk()
root.title("5.0 Surround Audio Player with VBAP")
root.geometry("1200x750")

# Load file
load_btn = tk.Button(root, text="Load File (.wav)", bg="lightblue", command=load_file, font=("Arial", 14), cursor="hand2")
load_btn.pack(pady=10)

status_label = tk.Label(root, text="No file loaded", fg='red', font=("Arial", 14))
status_label.pack()

layout = tk.Frame(root)
layout.pack(pady=20)

# Circular slider
slider = CircularSlider(root, radius=100, width=200, height=200)
slider.pack(pady=20)

# Play/Stop button
play_stop_button = tk.Button(root, text="Play", command=toggle_playback, bg="green", font=("Arial", 14), cursor="hand2")
play_stop_button.pack(pady=10)

# Music slider
slider_frame_main = tk.Frame(root)
slider_frame_main.pack(pady=10)

current_time_label = tk.Label(slider_frame_main, text="00:00", font=("Arial", 12))
current_time_label.pack(side=tk.LEFT)

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

duration_label = tk.Label(slider_frame_main, text="00:00", font=("Arial", 12))
duration_label.pack(side=tk.LEFT)

# Volume
slider_frame = tk.Frame(root)
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

# Run app
update_music_slider()
print("Audio device configuration: ", 2.0 if force_stereo else 5.0)
root.mainloop()
