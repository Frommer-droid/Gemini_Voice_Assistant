# -*- coding: utf-8 -*-
from app.utils.logging_utils import log_message


def get_microphone_list():
    """
    Возвращает список физических микрофонов, исключая виртуальные и дубликаты.
    Показывает ПОЛНЫЕ имена как в настройках Windows.
    """
    try:
        import sounddevice as sd

        devices = sd.query_devices()
        microphones = []
        exclude_keywords = [
            "stereo mix",
            "wave out",
            "loopback",
            "what u hear",
            "wasapi",
            "kernel streaming",
            "wdm-ks",
            "wdm",
            "primary sound",
            "communications",
            "recording control",
            "volume control",
            "output",
            "speaker",
            "headphone",
            "playback",
            "render",
            "line out",
            "spdif",
            "digital output",
            "hdmi",
            "optical",
            "wave:",
            "microsoft",
            "virtual",
            "cable",
            "voicemeeter",
            "vb-audio",
            "переназначение",
            "по умолчанию",
        ]
        seen_names = set()
        for i, d in enumerate(devices):
            if d.get("max_input_channels", 0) > 0:
                device_name = d.get("name", "").lower()
                original_name = d.get("name", "")  # полное имя!
                if any(keyword in device_name for keyword in exclude_keywords):
                    continue
                hostapi = d.get("hostapi", -1)
                try:
                    hostapi_info = sd.query_hostapis(hostapi)
                    hostapi_name = hostapi_info.get("name", "").lower()
                    if "mme" not in hostapi_name:
                        continue
                except Exception:
                    pass
                if original_name.lower() in seen_names:
                    continue
                seen_names.add(original_name.lower())

                # Показываем ПОЛНОЕ имя устройства без обработки
                display_name = original_name

                log_message(f"  Устройство: '{original_name}' -> '{display_name}'")

                microphones.append((i, display_name))
        return microphones
    except Exception as e:
        print(f"Ошибка получения микрофонов: {e}")
        return []
