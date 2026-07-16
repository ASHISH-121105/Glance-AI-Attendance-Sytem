import io
import os
import json
import base64
import librosa
import numpy as np
from resemblyzer import VoiceEncoder, preprocess_wav
from sklearn.svm import SVC
from pydub import AudioSegment

try:
    import noisereduce as nr
    HAS_NOISEREDUCE = True
except ImportError:
    HAS_NOISEREDUCE = False

if os.path.exists(os.path.join(os.getcwd(), "ffmpeg.exe")):
    AudioSegment.converter = os.path.join(os.getcwd(), "ffmpeg.exe")
    AudioSegment.ffprobe = os.path.join(os.getcwd(), "ffprobe.exe")

class VoicePipeline:
    def __init__(self):
        """
        Initialize the deep learning voice encoder model.
        This pre-allocates the neural network weights into memory.
        """
        self.encoder = VoiceEncoder()

    def extract_voice_embedding(self, voice_base64):
        """
        Takes a raw base64 payload string, applies defensive noise filtering,
        transcodes it, normalizes sample rates, and extracts a 256-d vocal vector.
        """
        try:
            print("📦 Pipeline: Parsing and decoding incoming Base64 browser payload...")
            if ';base64,' in voice_base64:
                _, voice_str = voice_base64.split(';base64,')
            else:
                voice_str = voice_base64
            
            raw_audio_bytes = base64.b64decode(voice_str)
            input_audio_stream = io.BytesIO(raw_audio_bytes)
            
            print("🔄 Pipeline: Transcoding and applying audio DSP filters via pydub...")
            audio_segment = AudioSegment.from_file(input_audio_stream)
            
            # --- DSP STEP 1: HIGH-PASS FILTER & NORMALIZATION ---
            # Cut off everything below 100Hz (destroys low-end AC rumbles and fan hums)
            # Normalize matches gain levels so quiet student voices aren't lost in floor noise
            audio_segment = audio_segment.high_pass_filter(100).normalize()
            
            # Export to an in-memory true PCM/WAV buffer
            wav_buffer = io.BytesIO()
            audio_segment.export(wav_buffer, format="wav")
            wav_buffer.seek(0)
            
            print("🎛️ Pipeline: Loading waveform and forcing downsample to 16,000 Hz...")
            audio_waveform, sample_rate = librosa.load(
                wav_buffer, 
                sr=16000, 
                mono=True
            )
            
            # --- DSP STEP 2: SPECTRAL NOISE SUBTRACTION (Optional Drop-in) ---
            if HAS_NOISEREDUCE:
                print("🛡️ Pipeline: Executing stationary noise reduction algorithm...")
                # Stationary noise reduction automatically profiles and masks background static
                audio_waveform = nr.reduce_noise(y=audio_waveform, sr=16000, prop_decrease=0.85)
            else:
                print("⚠️ Pipeline: Skipping advanced noise reduction (noisereduce library not installed).")

            print("✂️ Pipeline: Trimming remaining silent dead spaces...")
            processed_wav = VoiceEncoder.preprocess_wav(audio_waveform)
            
            print("🧠 Pipeline: Generating 256-dimensional structural vocal vector...")
            speaker_embedding = self.encoder.embed_utterance(processed_wav)
            
            return list(speaker_embedding.astype(float))
            
        except Exception as e:
            print(f"❌ Resemblyzer Pipeline Extraction Exception: {e}")
            return None

    def train_voice_classifier(self):
        """
        Fetches all 256-dimensional voice encodings and fits a multi-class SVM classifier.
        """
        from users.models import StudentProfile
        
        profiles = StudentProfile.objects.filter(is_voice_registered=True)
        if not profiles.exists():
            print("Training Aborted: No registered voice nodes present.")
            return None
            
        X, y = [], []
        for profile in profiles:
            if profile.voice_encoding:
                vector = json.loads(profile.voice_encoding)
                X.append(vector)
                y.append(profile.roll_number)
                
        if len(X) == 0:
            return None
            
        X_train = np.array(X)
        y_train = np.array(y)
        
        # Use a soft-margin SVC to better handle vectors slightly warped by noise artifacts
        clf = SVC(kernel='linear', probability=True, C=1.0)
        clf.fit(X_train, y_train)
        
        print(f"Voice SVM Matrix Synced successfully for {len(X_train)} student profiles.")
        return clf