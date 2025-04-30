import tkinter as tk

import sounddevice as sd
import soundfile as sf
import numpy as np
from math import cos, sin, radians

# Global variables for window and canvas size
center_x = 300
center_y = 300
is_playing = False

# Create the window and canvas
def setup_window(audio):
    root = tk.Tk()
    root.title("5.0 Speaker Configuration")
    root.geometry("600x700")

    # Canvas for the listener
    canvas = tk.Canvas(root, width=600, height=600, bg='white')
    canvas.pack()

    # Draw the listener (in the middle of the canvas)
    listener = canvas.create_oval(
        center_x - 20, center_y - 20, center_x + 20, center_y + 20,
        fill="blue", outline="black", width=2
    )

    # Speaker positions (x, y) around the listener
    speaker_positions = [
        (center_x - 150, center_y - 150),  # Front Left
        (center_x + 150, center_y - 150),  # Front Right
        (center_x - 150, center_y + 150),  # Rear Left
        (center_x + 150, center_y + 150),  # Rear Right
        (center_x, center_y - 250),        # Center
    ]

    speaker_names = [
        ("Front Left", 315),
        ("Front Right", 45),
        ("Rear Left", 270),
        ("Rear Right", 135),
        ("Center", 0)
    ]

    # Add buttons as speakers
    for i, (name, speaker_azimuth) in enumerate(speaker_names):
        x, y = speaker_positions[i]

        # Create a speaker button
        btn = tk.Button(
            root,
            text=f"{name}\n({speaker_azimuth})",
            bg="red",
            fg="white",
            command=lambda name=name: speaker_clicked(name, speaker_azimuth, audio)
        )
        # Place it at the corresponding position
        btn.place(x=x-30, y=y-30, width=60, height=60)

    # Play/Stop button
    play_stop_button = tk.Button(root, text="Play", command=lambda: toggle_play_stop(play_stop_button, audio))
    play_stop_button.pack(pady=20)

    # Start the Tkinter main loop
    root.mainloop()

# Toggle the play/stop button state
def toggle_play_stop(button, audio):
    global is_playing
    if is_playing:
        button.config(text="Play")
        is_playing = False
        print("Audio Stopped.")
        sd.stop()
        # You would insert actual code to stop the sound here
    else:
        button.config(text="Stop")
        is_playing = True
        print("Audio Playing.")
        panned_audio = vector_based_amplitude_panning_5_0(audio, 0, fs)
        sd.play(panned_audio, fs)

# Handle click event on speaker
def speaker_clicked(speaker_name, speaker_azimuth, audio):
    sd.stop()
    print(f"Playing sound from {speaker_name}, azimuth: {speaker_azimuth}")
    panned_audio = vector_based_amplitude_panning_5_0(audio, speaker_azimuth, fs)
    sd.play(panned_audio, fs)
    sd.wait()


#############################################################################################

# Vector-Based Amplitude Panning (VBAP) for 5.0 speaker setup
def vector_based_amplitude_panning_5_0(audio, azimuth, fs):
    azimuth = azimuth % 360
    
    azimuth_rad = np.radians(azimuth)

    speaker_vectors = np.array([ 
        [cos(radians(-45)), sin(radians(-45))],  # Front Left (FL)
        [cos(radians(0)), sin(radians(0))],      # Front Center (FC)
        [cos(radians(45)), sin(radians(45))],    # Front Right (FR)
        [cos(radians(-135)), sin(radians(-135))], # Rear Left (RL)
        [cos(radians(135)), sin(radians(135))],  # Rear Right (RR)
    ])
    
    source_vector = np.array([cos(azimuth_rad), sin(azimuth_rad)])
    
    gains = np.clip(np.dot(speaker_vectors, source_vector), 0, 1)
    
    panned_audio = np.vstack([ 
        gains[0] * audio,  # Front Left (FL)
        gains[1] * audio,  # Front Center (FC)
        gains[2] * audio,  # Front Right (FR)
        gains[3] * audio,  # Rear Left (RL)
        gains[4] * audio   # Rear Right (RR)
    ]).T 
    
    return panned_audio

file_path = 'lp.wav'
audio, fs = sf.read(file_path)

if audio.ndim > 1:
    audio = np.mean(audio, axis=1)


# Start app
if __name__ == "__main__":
    setup_window(audio)
