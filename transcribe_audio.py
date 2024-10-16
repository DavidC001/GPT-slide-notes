import torch
from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline
import librosa
import soundfile as sf
import os

# ----------------------------- Configuration ----------------------------- #

# Path configurations
audio_input_path = "C:\\Users\\david\\Documents\\Registrazioni di suoni\\KGE-2-10.m4a"
output_dir = "audios"
transcription_output = "transcriptions.txt"

# Model configuration
model_id = "openai/whisper-large-v3-turbo"

# ----------------------------- Setup ----------------------------- #

# Determine device and data type
device = 0 if torch.cuda.is_available() else -1  # Use GPU if available
torch_dtype = torch.float16 if torch.cuda.is_available() else torch.float32

# Create output directory if it doesn't exist
os.makedirs(output_dir, exist_ok=True)

# ----------------------------- Load Model ----------------------------- #

print("Loading Whisper model...")
model = AutoModelForSpeechSeq2Seq.from_pretrained(
    model_id,
    torch_dtype=torch_dtype,
    low_cpu_mem_usage=True,
    device_map="auto" if torch.cuda.is_available() else None,  # Automatically map layers to GPU
    use_safetensors=True
)
print("Model loaded successfully.")

# Load the processor
processor = AutoProcessor.from_pretrained(model_id)

# Initialize the ASR pipeline
asr_pipeline = pipeline(
    "automatic-speech-recognition",
    model=model,
    tokenizer=processor.tokenizer,
    feature_extractor=processor.feature_extractor,
    # device=device,  # -1 for CPU, 0 for first GPU
    chunk_length_s=30,  # Adjust based on your audio length and memory
    stride_length_s=5
)

# ----------------------------- Audio Conversion ----------------------------- #

def convert_audio_to_wav(input_path, output_path, target_sr=16000):
    """
    Converts an audio file to WAV format with the specified sample rate.
    """
    try:
        print(f"Loading audio file: {input_path}")
        y, sr = librosa.load(input_path, sr=target_sr)
        print(f"Saving converted audio to: {output_path}")
        sf.write(output_path, y, sr)
        print("Conversion successful.")
        return output_path
    except Exception as e:
        print(f"Error converting {input_path}: {e}")
        return None

# Convert the input audio
converted_audio_path = convert_audio_to_wav(
    audio_input_path,
    os.path.join(output_dir, "KGE-2-10.wav"),
    target_sr=16000
)

if not converted_audio_path:
    print("Audio conversion failed. Exiting.")
    exit(1)

# ----------------------------- Transcription ----------------------------- #

def transcribe_audio(pipeline, audio_path):
    """
    Transcribes the given audio file using the provided ASR pipeline.
    """
    try:
        print(f"Transcribing audio file: {audio_path}")
        result = pipeline(audio_path)
        transcription = result.get("text", "")
        print("Transcription successful.")
        return transcription
    except Exception as e:
        print(f"Error transcribing {audio_path}: {e}")
        return ""

# Perform transcription
transcription = transcribe_audio(asr_pipeline, converted_audio_path)

# ----------------------------- Save Transcription ----------------------------- #

def save_transcription(output_file, audio_path, transcription_text):
    """
    Saves the transcription to a text file.
    """
    try:
        with open(output_file, "a", encoding="utf-8") as f:
            f.write(f"Audio: {audio_path}\n")
            f.write(f"Transcription: {transcription_text}\n\n")
        print(f"Transcription saved to {output_file}")
    except Exception as e:
        print(f"Error saving transcription: {e}")

# Save the transcription
save_transcription(transcription_output, converted_audio_path, transcription)
