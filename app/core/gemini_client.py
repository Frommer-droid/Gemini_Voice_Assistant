# -*- coding: utf-8 -*-
import os
import socket
import ssl
import time
import traceback
from typing import Callable, Optional, Tuple

try:
    import httpx
except Exception:
    httpx = None

from google import genai
from google.genai import types

try:
    from google.genai import errors as genai_errors
except Exception:
    genai_errors = None

from app.core.app_config import MODEL_DISPLAY_NAMES, MODEL_FALLBACKS
from app.utils.logging_utils import log_message


class GeminiCancelledError(Exception):
    """Исключение для отменённых запросов к Gemini."""


class GeminiClientManager:
    def __init__(self, log_func=log_message) -> None:
        self.log = log_func
        self.client = None
        self._supported_thinking_levels = None
        thinking_fields = getattr(types.ThinkingConfig, "model_fields", {}) or {}
        self.supports_thinking_level = "thinking_level" in thinking_fields

    def initialize(self, settings: dict, vless_manager=None):
        # Загрузка API ключа ТОЛЬКО из настроек
        api_key = settings.get("gemini_api_key", "").strip()

        if not api_key:
            self.log("? API ключ Gemini не указан")
            self.log("   Откройте настройки (вкладка Gemini) и введите API ключ")
            self.client = None
            return None

        # Сбрасываем предыдущие настройки прокси, чтобы не использовать протухшие значения
        if "HTTPS_PROXY" in os.environ:
            os.environ.pop("HTTPS_PROXY", None)
            self.log("HTTPS_PROXY очищен")

        # VLESS VPN имеет приоритет над ручным прокси
        if (
            vless_manager
            and getattr(vless_manager, "is_running", False)
            and settings.get("vless_enabled", False)
        ):
            # Используем порт из VLESS VPN
            vless_port = vless_manager.local_socks_port
            os.environ["HTTPS_PROXY"] = f"socks5://127.0.0.1:{vless_port}"
            self.log(f"Прокси VLESS VPN: 127.0.0.1:{vless_port}")

        elif settings.get("proxy_enabled", False):
            # Используем ручной прокси (v2rayN)
            proxy_address = self._safe_str(settings.get("proxy_address", "127.0.0.1"))
            proxy_port = self._safe_str(settings.get("proxy_port", "10808"))
            os.environ["HTTPS_PROXY"] = f"socks5://{proxy_address}:{proxy_port}"
            self.log(f"Прокси v2rayN: {proxy_address}:{proxy_port}")
        else:
            self.log("Прокси для Gemini не используется")

        try:
            http_options = None
            if httpx is not None:
                try:
                    timeout = httpx.Timeout(
                        connect=10.0, read=60.0, write=30.0, pool=60.0
                    )
                    proxy = os.environ.get("HTTPS_PROXY") or None
                    proxy_display = proxy or "none"
                    http_client = httpx.Client(
                        timeout=timeout,
                        http2=False,
                        trust_env=True,
                        proxies=proxy,
                    )
                    http_options = types.HttpOptions(
                        timeout=65000,
                        retry_options=types.HttpRetryOptions(attempts=3),
                        httpx_client=http_client,
                    )
                    self.log(
                        "HTTP клиент Gemini настроен: "
                        f"http2=off, retries=3, connect_timeout=10s, proxy={proxy_display}"
                    )
                except Exception as e:
                    self.log(f"? Не удалось настроить кастомный HTTP клиент: {e}")

            self.client = genai.Client(api_key=api_key, http_options=http_options)
            self.log("Gemini клиент инициализирован")
        except Exception as e:
            self.client = None
            self.log(f"Ошибка инициализации Gemini: {e}")
            self.log(traceback.format_exc())
        return self.client

    def reinitialize(self, settings: dict, vless_manager=None):
        return self.initialize(settings, vless_manager=vless_manager)

    def describe_model(self, model_name: str, thinking_level: str) -> str:
        level = (thinking_level or "low").lower()
        key = (model_name, level)
        return MODEL_DISPLAY_NAMES.get(key, f"{model_name} ({level})")

    def determine_thinking_level(
        self, settings: dict, use_pro: bool, use_flash: bool, model_name: Optional[str]
    ) -> str:
        """
        Определяет уровень мышления (thinking_level) на основе настроек.
        Gemini 3.x: поддерживаемые уровни зависят от SDK.
        """
        # Если явный флаг Pro или модель Pro
        if use_pro or (model_name and "pro" in model_name.lower()):
            val = settings.get("gemini3_pro_thinking_level", "high")
            return self._normalize_thinking_level(val)

        # В остальных случаях (Flash, по умолчанию)
        val = settings.get("gemini3_flash_thinking_level", "high")
        return self._normalize_thinking_level(val)

    def generate_with_fallback(
        self,
        model_name: str,
        prompt: str,
        thinking_level: str,
        settings: dict,
        cancel_check: Optional[Callable[[], bool]] = None,
        status_cb: Optional[Callable[[str, str, bool], None]] = None,
        warning_color: Optional[str] = None,
    ) -> Tuple[object, str, str]:
        """Отправляет запрос к Gemini, понижая модель при ошибках или недоступности."""
        if not self.client:
            raise RuntimeError("Gemini client не инициализирован")

        attempted = set()
        current_model = model_name
        current_level = thinking_level or "low"
        retries_for_model = 0
        max_retries = 2

        while True:
            if cancel_check and cancel_check():
                raise GeminiCancelledError("Gemini generation cancelled")

            attempted.add(current_model)
            config = self._build_generation_config(current_level)

            try:
                response = self.client.models.generate_content(
                    model=current_model, contents=prompt, config=config
                )
                retries_for_model = 0
                return response, current_model, current_level
            except GeminiCancelledError:
                raise
            except Exception as e:
                display_name = self.describe_model(current_model, current_level)

                if self._is_transient_network_error(e) and retries_for_model < max_retries:
                    retries_for_model += 1
                    delay = min(6.0, 1.5**retries_for_model)
                    self.log(
                        f"{display_name}: сетевой сбой ({e}). "
                        f"Повтор {retries_for_model}/{max_retries} через {delay:.1f}с"
                    )
                    time.sleep(delay)
                    continue

                self.log(f"Ошибка {display_name}: {e}")
                fallback_model = MODEL_FALLBACKS.get(current_model)
                should_fallback = (
                    fallback_model
                    and fallback_model not in attempted
                    and self._should_try_fallback(e)
                    and not (cancel_check and cancel_check())
                )

                if should_fallback:
                    fallback_display = self.describe_model(
                        fallback_model, current_level
                    )
                    if status_cb and warning_color:
                        status_cb(
                            f"{display_name} недоступна  {fallback_display}",
                            warning_color,
                            True,
                        )
                    self.log(
                        f"{display_name} недоступна ({e}). "
                        f"Переключаемся на {fallback_display}"
                    )
                    current_model = fallback_model
                    # Recalculate level for the new model (preserving flags if possible, or inferring)
                    current_level = self.determine_thinking_level(
                        settings, False, False, model_name=current_model
                    )
                    retries_for_model = 0
                    continue

                raise

    def resolve_command(
        self, description: str, cancel_check: Optional[Callable[[], bool]] = None
    ) -> str:
        """
        Использует Gemini для определения команды по описанию.
        Возвращает команду или 'UNKNOWN' если не уверен.
        """
        if not self.client:
            return "UNKNOWN"

        if cancel_check and cancel_check():
            return "UNKNOWN"

        try:
            model_name = "gemini-3-flash-preview"  # Используем новую быструю модель

            prompt = f"""
            Ты - эксперт по Windows командам и программам. Определи точную команду для запуска по описанию пользователя.

            Описание: "{description}"

            Правила:
            1. Верни ТОЛЬКО команду (например: "notepad", "calc", "control", "chrome")
            2. Если это программа - верни её исполняемое имя или путь
            3. Если команда может быть опасна (удаление, форматирование, модификация реестра) - верни её, но с префиксом "DANGER:"
            4. Если не уверен или описание нечёткое - верни "UNKNOWN"
            5. Не пиши объяснений, только команду

            Примеры:
            - "калькулятор"  "calc"
            - "редактор кода"  "code"
            - "браузер"  "chrome"
            - "удали все файлы"  "DANGER:del /f /q *.*"
            - "что-то непонятное"  "UNKNOWN"
            """

            response = self._generate_simple(
                model_name, prompt, temperature=0.0, cancel_check=cancel_check
            )
            if response is None:
                return "UNKNOWN"

            if cancel_check and cancel_check():
                return "UNKNOWN"

            result = (getattr(response, "text", "") or "").strip()
            self.log(f"Gemini command resolution: '{description}' -> '{result}'")

            if not result:
                return "UNKNOWN"

            # Берём первую строку и убираем кавычки по краям
            first_line = result.splitlines()[0].strip()
            cleaned = first_line.strip()
            if (
                cleaned.startswith(("'", '"'))
                and cleaned.endswith(("'", '"'))
                and len(cleaned) > 1
            ):
                cleaned = cleaned[1:-1]

            # Принимаем любую непустую строку, кроме явного UNKNOWN
            if cleaned.upper() == "UNKNOWN":
                return "UNKNOWN"
            return cleaned

        except Exception as e:
            self.log(f"Ошибка при определении команды через Gemini: {e}")
            return "UNKNOWN"

    def resolve_url(self, description: str) -> str:
        """
        Использует Gemini для определения URL по описанию.
        Возвращает URL или 'SEARCH' если не уверен.
        """
        if not self.client:
            return "SEARCH"

        try:
            model_name = "gemini-3-flash-preview"  # Используем новую быструю модель

            prompt = f"""
            Ты - умный помощник для навигации. Твоя задача - найти точный URL веб-сайта по описанию пользователя.

            Описание от пользователя: "{description}"

            Правила:
            1. Если ты знаешь точный официальный URL этого сайта, верни ТОЛЬКО его (например: https://example.com).
            2. Если описание нечеткое или ты не уверен в адресе, верни слово SEARCH.
            3. Если это запрос на поиск (например "найди картинки котиков"), верни SEARCH.
            4. Не пиши никаких объяснений, только URL или SEARCH.
            """

            response = self._generate_simple(
                model_name, prompt, temperature=0.0, cancel_check=None
            )
            if response is None:
                return "SEARCH"

            result = (getattr(response, "text", "") or "").strip()
            self.log(f"Gemini URL resolution: '{description}' -> '{result}'")

            if result.startswith("http") or result.startswith("www"):
                return result
            return "SEARCH"

        except Exception as e:
            self.log(f"Ошибка при определении URL через Gemini: {e}")
            return "SEARCH"

    def _generate_simple(
        self,
        model_name: str,
        prompt: str,
        temperature: float,
        cancel_check: Optional[Callable[[], bool]] = None,
    ):
        if not self.client:
            return None
        if cancel_check and cancel_check():
            return None
        response = self.client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(temperature=temperature),
        )
        return response

    def _get_supported_thinking_levels(self):
        if self._supported_thinking_levels is not None:
            return self._supported_thinking_levels
        levels = set()
        try:
            enum_cls = getattr(types, "ThinkingLevel", None)
            if enum_cls:
                levels = {str(level.name).upper() for level in enum_cls}
        except Exception:
            levels = set()
        levels.discard("THINKING_LEVEL_UNSPECIFIED")
        self._supported_thinking_levels = levels or None
        return self._supported_thinking_levels

    def _normalize_thinking_level(self, level: str) -> str:
        normalized = (level or "HIGH").upper()
        allowed = self._get_supported_thinking_levels()
        if not allowed or normalized in allowed:
            return normalized
        fallback = None
        if normalized in ("MINIMAL", "MEDIUM") and "LOW" in allowed:
            fallback = "LOW"
        elif "HIGH" in allowed:
            fallback = "HIGH"
        elif "LOW" in allowed:
            fallback = "LOW"
        else:
            fallback = next(iter(allowed))
        if fallback != normalized:
            self.log(
                f"thinking_level '{normalized}' не поддерживается SDK, используем '{fallback}'."
            )
        return fallback

    def _build_generation_config(self, thinking_level: str):
        """Собирает конфиг с учетом особенностей моделей 3.x."""
        # Gemini 3.x: используют thinking_level (поддерживаемые значения зависят от SDK)
        if self.supports_thinking_level:
            level = self._normalize_thinking_level(thinking_level)
            return types.GenerateContentConfig(
                thinking_config=types.ThinkingConfig(
                    thinking_level=level,
                    include_thoughts=False,
                )
            )

        # Fallback для старых SDK (если вдруг)
        return types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(thinking_budget=-1)
        )

    def _is_transient_network_error(self, error) -> bool:
        """Возвращает True для сетевых ошибок, которые можно повторить."""
        if httpx is not None and isinstance(
            error, (httpx.TransportError, httpx.TimeoutException)
        ):
            return True
        if isinstance(error, (socket.timeout, ConnectionError, ssl.SSLError)):
            return True
        return False

    def _should_try_fallback(self, error) -> bool:
        """Понимает, стоит ли пробовать резервную модель после ошибки."""
        retryable_codes = {403, 404, 408, 409, 429, 500, 502, 503}
        if genai_errors is not None and isinstance(error, genai_errors.ClientError):
            status_code = getattr(error, "status_code", None) or getattr(
                error, "code", None
            )
            if status_code in retryable_codes:
                return True
            text = str(error).lower()
            if any(
                keyword in text
                for keyword in (
                    "quota",
                    "exhausted",
                    "temporarily unavailable",
                    "unavailable",
                    "timeout",
                )
            ):
                return True
        if genai_errors is not None and isinstance(error, genai_errors.ServerError):
            return True

        if self._is_transient_network_error(error):
            return True

        return False

    @staticmethod
    def _safe_str(value) -> str:
        return str(value) if value is not None else ""
