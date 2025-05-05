# Full updated 5.0 VBAP surround sound audio player with GUI and proper 5-channel output.

import tkinter as tk
from tkinter import filedialog
import sounddevice as sd
import soundfile as sf
import numpy as np

# ======================== Global audio state ========================
audio_data = None
fs = 44100
pointer = 0
playing = False
stream = None
volume = 1.0
current_playing = None
slider_updating = False
vbap_gain = np.array([1.0]*5)  # For 5 speakers
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
        status_label.config(text=f"Loaded: {path.split('/')[-1]}")
        music_slider.config(to=int(len(audio_data) / fs))
        duration_label.config(text=format_time(len(audio_data) / fs))
        if not stream:
            start_stream()

def start_stream():
    global stream
    stream = sd.OutputStream(
        samplerate=fs,
        channels=5,
        callback=audio_callback
    )
    stream.start()

def audio_callback(outdata, frames, time, status):
    global pointer, playing, volume, vbap_gain

    if not playing or audio_data is None:
        outdata[:] = np.zeros((frames, 5))
        return

    end = pointer + frames
    chunk = audio_data[pointer:end]

    if len(chunk) < frames:
        chunk = np.concatenate([chunk, np.zeros((frames - len(chunk), audio_data.shape[1]))])
        playing = False
        update_all_buttons()

    if chunk.shape[1] == 1:
        mono_chunk = chunk[:, 0]
    else:
        mono_chunk = chunk[:, 0]

    output = np.zeros((frames, 5))
    for i in range(5):
        output[:, i] = mono_chunk * vbap_gain[i] * volume

    outdata[:] = output
    pointer += frames

def toggle_playback(speaker_name):
    global playing, pointer, current_playing

    if audio_data is None:
        return

    if current_playing and current_playing != speaker_name:
        stop_playback(current_playing)

    if playing and current_playing == speaker_name:
        stop_playback(speaker_name)
    else:
        start_playback(speaker_name)

def start_playback(speaker_name):
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

def stop_playback(speaker_name):
    global playing, current_playing, stream
    playing = False
    current_playing = None
    if stream:
        stream.stop()
    update_button(speaker_name)

# ======================== GUI Update Helpers ========================
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

# ======================== VBAP Gain for 5 speakers ========================
def normalize(v):
    """Normalize a vector to unit power."""
    norm = np.linalg.norm(v)
    return v / norm if norm > 0 else v


def calculate_vbap_gain(source_angle_deg):
    speaker_angles = [-30, 30, 0, -110, 110]
    speaker_names = ["FL", "FR", "C", "RL", "RR"]
    speaker_pairs = [
        (0, 2),  # FL - C
        (1, 2),  # FR - C
        (0, 3),  # FL - RL
        (1, 4),  # FR - RR
        (3, 4),  # RL - RR
    ]

    source_angle_rad = np.radians(source_angle_deg)
    source_vec = np.array([np.cos(source_angle_rad), np.sin(source_angle_rad)])

    best_gains = None
    best_pair = None
    best_alignment = -np.inf

    for i, j in speaker_pairs:
        v1 = np.array([np.cos(np.radians(speaker_angles[i])), np.sin(np.radians(speaker_angles[i]))])
        v2 = np.array([np.cos(np.radians(speaker_angles[j])), np.sin(np.radians(speaker_angles[j]))])
        L = np.column_stack((v1, v2))

        try:
            L_inv = np.linalg.inv(L)
        except np.linalg.LinAlgError:
            continue

        gains_pair = np.dot(L_inv, source_vec)

        if np.all(gains_pair >= 0):  # Only accept positive gains
            gains_pair = normalize(gains_pair)
            gains_full = np.zeros(len(speaker_angles))
            gains_full[i] = gains_pair[0]
            gains_full[j] = gains_pair[1]

            # Compute alignment score (dot product with source direction)
            approx_vec = gains_pair[0] * v1 + gains_pair[1] * v2
            alignment = np.dot(normalize(approx_vec), normalize(source_vec))

            if alignment > best_alignment:
                best_alignment = alignment
                best_gains = gains_full
                best_pair = (speaker_names[i], speaker_names[j], speaker_angles[i], speaker_angles[j])

    print(source_angle_deg, best_gains, best_pair)
    return best_gains if best_gains is not None else np.zeros(5)

# ======================== GUI Setup ========================
root = tk.Tk()
root.title("5.0 Surround Audio Player with VBAP")
root.geometry("1200x700")

load_btn = tk.Button(root, text="Load File (.wav)", bg="lightblue", command=load_file, font=("Arial", 14))
load_btn.pack(pady=10)

status_label = tk.Label(root, text="No file loaded", foreground='red', font=("Arial", 14))
status_label.pack()

layout = tk.Frame(root)
layout.pack(pady=20)

grid_layout = tk.Frame(layout)
grid_layout.grid(row=0, column=0, pady=10)

btn_c = tk.Button(grid_layout, text="Center (0°) 🔊", width=20, height=2, font=("Arial", 14), bg="green", command=lambda: toggle_playback("Center"))
btn_c.grid(row=0, column=1, padx=20, pady=20)

btn_l = tk.Button(grid_layout, text="Left (-30°) 🔊", width=15, height=2, font=("Arial", 14), bg="green", command=lambda: toggle_playback("Left"))
btn_l.grid(row=1, column=0, padx=20, pady=20)

btn_r = tk.Button(grid_layout, text="Right (30°) 🔊", width=15, height=2, font=("Arial", 14), bg="green", command=lambda: toggle_playback("Right"))
btn_r.grid(row=1, column=2, padx=20, pady=20)

btn_rl = tk.Button(grid_layout, text="Rear Left (-110°) 🔊", width=20, height=2, font=("Arial", 14), bg="green", command=lambda: toggle_playback("Rear Left"))
btn_rl.grid(row=2, column=0, padx=20, pady=20)

btn_rr = tk.Button(grid_layout, text="Rear Right (110°) 🔊", width=20, height=2, font=("Arial", 14), bg="green", command=lambda: toggle_playback("Rear Right"))
btn_rr.grid(row=2, column=2, padx=20, pady=20)

control_buttons["Center"] = btn_c
control_buttons["Left"] = btn_l
control_buttons["Right"] = btn_r
control_buttons["Rear Left"] = btn_rl
control_buttons["Rear Right"] = btn_rr

listener_label = tk.Label(layout, text="🧍", font=("Arial", 40))
listener_label.place(relx=0.5, rely=0.5, anchor="center")

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
    command=on_music_slider_change
)
music_slider.pack(side=tk.LEFT, padx=10)

duration_label = tk.Label(slider_frame_main, text="00:00", font=("Arial", 12))
duration_label.pack(side=tk.LEFT)

slider_frame = tk.Frame(root)
slider_frame.pack(side=tk.RIGHT, padx=30, anchor="n")

tk.Label(slider_frame, text="Volume", font=("Arial", 16)).pack(pady=10)
volume_slider = tk.Scale(
    slider_frame,
    from_=100,
    to=0,
    orient=tk.VERTICAL,
    command=on_volume_change,
    length=300,
    font=("Arial", 12)
)
volume_slider.set(50)
volume_slider.pack()

update_music_slider()
root.mainloop()

