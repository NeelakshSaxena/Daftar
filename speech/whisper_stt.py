import os

# ✅ FORCE LOCAL MODEL STORAGE
BASE_DIR = "G:/Projects/MCPs/Daftar/speech/models"
os.environ["HF_HOME"] = BASE_DIR
os.environ["TRANSFORMERS_CACHE"] = BASE_DIR
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

import customtkinter as ctk
import sounddevice as sd
import numpy as np
import queue
import threading

from transformers import pipeline

# ========== CONFIG ==========
MODEL_NAME = "openai/whisper-small"   # 🔥 upgraded
SAMPLE_RATE = 16000
CHUNK_SECONDS = 5                      # 🔥 more context
# ============================

model = None
audio_queue = queue.Queue()
recording = False
last_text = ""   # 🔥 prevent duplicates


# ========== LOAD MODEL ==========
def load_model():
    global model

    status_label.configure(text="Loading model... ⚡")
    progress_bar.set(0.3)

    try:
        model = pipeline(
            "automatic-speech-recognition",
            model=MODEL_NAME,
            device=0  # GPU
        )
        status_label.configure(text="Model Ready (GPU) 🚀")

    except Exception as e:
        print("GPU failed, falling back to CPU:", e)
        model = pipeline(
            "automatic-speech-recognition",
            model=MODEL_NAME,
            device=-1
        )
        status_label.configure(text="Model Ready (CPU) ⚠️")

    progress_bar.set(1)
    btn.configure(state="normal", text="Record", command=start_recording)


def load_model_thread():
    btn.configure(state="disabled")
    threading.Thread(target=load_model, daemon=True).start()


# ========== AUDIO ==========
def audio_callback(indata, frames, time, status):
    if recording:
        audio_queue.put(indata.copy())


def start_recording():
    global recording, model

    if model is None:
        load_model_thread()
        return

    recording = True
    btn.configure(text="Stop", command=stop_recording)
    status_label.configure(text="Listening... 🎤")

    threading.Thread(target=process_audio, daemon=True).start()


def stop_recording():
    global recording
    recording = False
    btn.configure(text="Record", command=start_recording)
    status_label.configure(text="Stopped")


def process_audio():
    global last_text

    buffer = np.zeros((0, 1), dtype=np.float32)

    with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, callback=audio_callback):
        while recording:
            try:
                data = audio_queue.get(timeout=1)
                buffer = np.concatenate((buffer, data))

                if len(buffer) >= SAMPLE_RATE * CHUNK_SECONDS:
                    audio_chunk = buffer.flatten()

                    try:
                        result = model(
                            audio_chunk,
                            generate_kwargs={
                                "language": "en",
                                "task": "transcribe",
                                "temperature": 0.0
                            }
                        )

                        text = result["text"].strip()

                        # ✅ avoid duplicates
                        if text and text != last_text:
                            text_box.insert("end", text + "\n")
                            text_box.see("end")
                            last_text = text

                    except Exception as e:
                        print("Inference error:", e)

                    # ✅ better overlap (less repetition)
                    buffer = buffer[int(SAMPLE_RATE * 2):]

            except queue.Empty:
                continue


# ========== UI ==========
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

app = ctk.CTk()
app.title("⚡ Real-Time Speech to Text (Whisper Medium)")
app.geometry("700x500")

title = ctk.CTkLabel(
    app,
    text="🎙️ Live Speech Recognition (Improved)",
    font=("Arial", 22, "bold")
)
title.pack(pady=10)

status_label = ctk.CTkLabel(app, text="Idle", font=("Arial", 14))
status_label.pack(pady=5)

btn = ctk.CTkButton(
    app,
    text="Load Model",
    command=load_model_thread,
    width=220,
    height=50,
    font=("Arial", 16)
)
btn.pack(pady=10)

progress_bar = ctk.CTkProgressBar(app, width=400)
progress_bar.set(0)
progress_bar.pack(pady=10)

text_box = ctk.CTkTextbox(
    app,
    width=600,
    height=280,
    font=("Arial", 14)
)
text_box.pack(pady=10)

app.mainloop()