# -*- coding: utf-8 -*-
"""Аудио-пайплайн ассистента."""

import threading
import winsound

from app.core.app_config import SOUND_SCHEMES
from app.speech import whisper_pipeline


class VoiceAssistantAudioMixin:
    def setup_audio(self):
        whisper_pipeline.setup_audio(self)

    def setup_whisper(self, model_name=None):
        return whisper_pipeline.setup_whisper(self, model_name)

    def is_model_downloaded(self, model_name):
        """Проверяет наличие папки модели."""
        return self.whisper_engine.is_model_downloaded(model_name)

    def start_recording(self, continuous=False, source=None):
        whisper_pipeline.start_recording(self, continuous, source)

    def stop_recording(self, continuous=False):
        whisper_pipeline.stop_recording(self, continuous)

    def _record_audio(self, continuous=False):
        whisper_pipeline.record_audio(self, continuous)

    def _should_skip_silence(self, audio_samples, chunk_peak):
        return whisper_pipeline.should_skip_silence(self, audio_samples, chunk_peak)

    def _process_continuous_segment(self, audio_np):
        whisper_pipeline.process_continuous_segment(self, audio_np)

    def _process_audio_whisper(self, audio_np, is_final_segment=False):
        whisper_pipeline.process_audio_whisper(self, audio_np, is_final_segment)

    def play_sound(self, sound_type):
        scheme = self.settings.get("sound_scheme")
        if scheme == "Отключены":
            return

        sounds = SOUND_SCHEMES.get(scheme, {})
        if sound_type in sounds:
            freq, duration = sounds[sound_type]
            threading.Thread(
                target=lambda: winsound.Beep(freq, duration), daemon=True
            ).start()
