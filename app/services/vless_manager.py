# -*- coding: utf-8 -*-
"""
VLESS VPN Manager для Gemini Voice Assistant
Управление VLESS подключением через xray-core или v2ray-core
"""

import json
import os
import socket
import subprocess
import sys
import time
from urllib.parse import unquote

from app.core.app_config import get_exe_directory


class VLESSManager:
    """Менеджер для управления VLESS VPN подключением"""

    def __init__(self, log_func=print, socks_port=10809):
        """
        Инициализация менеджера

        Args:
            log_func: функция для логирования (по умолчанию print)
        """
        self.log = log_func
        self.xray_process = None
        self.is_running = False
        self.local_socks_port = socks_port  # ← Теперь можно передать
        self.xray_exe = self._find_xray_executable()
        self.config_file = None

    def _find_xray_executable(self):
        """Поиск xray.exe или v2ray.exe в папке с программой"""
        if getattr(sys, "frozen", False):
            # Для скомпилированного приложения
            exe_dir = get_exe_directory()
            # Проверяем папку _internal
            internal_dir = os.path.join(exe_dir, "_internal")
        else:
            # Для исходников
            exe_dir = get_exe_directory()
            internal_dir = exe_dir

        # Список мест для поиска (в порядке приоритета)
        search_dirs = [
            internal_dir,  # Сначала _internal (для скомпилированного)
            exe_dir,  # Потом корень (для исходников)
        ]

        for search_dir in search_dirs:
            # Пробуем найти xray.exe (приоритетный)
            xray_path = os.path.join(search_dir, "xray.exe")
            if os.path.exists(xray_path):
                self.log(f"✓ Найден xray.exe: {xray_path}")
                return xray_path

            # Если нет xray.exe, ищем v2ray.exe (альтернатива)
            v2ray_path = os.path.join(search_dir, "v2ray.exe")
            if os.path.exists(v2ray_path):
                self.log(f"✓ Найден v2ray.exe: {v2ray_path}")
                return v2ray_path

        # Ничего не найдено
        self.log("⚠ ПРЕДУПРЕЖДЕНИЕ: xray.exe или v2ray.exe не найдены")
        self.log(f"   Искал в: {', '.join(search_dirs)}")
        self.log("  Для работы VLESS скачайте:")
        self.log("  - xray-core: https://github.com/XTLS/Xray-core/releases")
        self.log("  - v2ray-core: https://github.com/v2fly/v2ray-core/releases")
        return None

    def parse_vless_url(self, vless_url):
        """
        Парсинг VLESS URL в параметры подключения

        Args:
            vless_url: строка формата vless://uuid@server:port?params#name

        Returns:
            dict с параметрами подключения или None при ошибке
        """
        try:
            # Убираем пробелы
            vless_url = vless_url.strip()

            # Формат: vless://uuid@server:port?params#name
            if not vless_url.startswith("vless://"):
                self.log("❌ ОШИБКА: URL должен начинаться с vless://")
                return None

            # Убираем префикс
            url_content = vless_url[8:]

            # Разделяем на части
            if "#" in url_content:
                url_part, name = url_content.rsplit("#", 1)
                name = unquote(name)
            else:
                url_part = url_content
                name = "VLESS Connection"

            # Разделяем на uuid@server:port и параметры
            if "?" in url_part:
                connection_part, params_part = url_part.split("?", 1)
            else:
                connection_part = url_part
                params_part = ""

            # Парсим uuid@server:port
            if "@" not in connection_part:
                self.log("❌ ОШИБКА: Неверный формат (нет @)")
                return None

            uuid, server_port = connection_part.split("@", 1)

            if ":" not in server_port:
                self.log("❌ ОШИБКА: Неверный формат (нет порта)")
                return None

            server, port = server_port.rsplit(":", 1)

            # Парсим параметры
            params = {}
            if params_part:
                for param in params_part.split("&"):
                    if "=" in param:
                        key, value = param.split("=", 1)
                        params[key] = unquote(value)

            # Формируем результат
            result = {
                "uuid": uuid,
                "server": server,
                "port": int(port),
                "network": params.get("type", "tcp"),
                "security": params.get("security", "none"),
                "flow": params.get("flow", ""),
                "sni": params.get("sni", server),
                "alpn": params.get("alpn", ""),
                "fp": params.get("fp", ""),
                "pbk": params.get("pbk", ""),
                "sid": params.get("sid", ""),
                "spx": params.get("spx", ""),
                "path": params.get("path", "/"),
                "host": params.get("host", ""),
                "serviceName": params.get("serviceName", ""),
                "name": name,
            }

            self.log(f"✓ VLESS URL распознан: {result['name']}")
            self.log(f"  📡 Сервер: {result['server']}:{result['port']}")
            self.log(f"  🔒 Протокол: {result['network']}/{result['security']}")

            return result

        except Exception as e:
            self.log(f"❌ ОШИБКА парсинга VLESS URL: {e}")
            import traceback

            self.log(traceback.format_exc())
            return None

    def generate_xray_config(self, vless_params):
        """
        Генерация конфигурационного файла для xray-core/v2ray-core

        Args:
            vless_params: параметры подключения из parse_vless_url()

        Returns:
            dict с конфигурацией
        """
        # Базовая конфигурация
        config = {
            "log": {"loglevel": "warning"},
            "inbounds": [
                {
                    "port": self.local_socks_port,
                    "listen": "127.0.0.1",
                    "protocol": "socks",
                    "settings": {"auth": "noauth", "udp": True},
                }
            ],
            "outbounds": [
                {
                    "protocol": "vless",
                    "settings": {
                        "vnext": [
                            {
                                "address": vless_params["server"],
                                "port": vless_params["port"],
                                "users": [
                                    {
                                        "id": vless_params["uuid"],
                                        "encryption": "none",
                                        "flow": vless_params.get("flow", ""),
                                    }
                                ],
                            }
                        ]
                    },
                    "streamSettings": {"network": vless_params["network"]},
                }
            ],
        }

        # Настройка security (TLS/Reality)
        security = vless_params.get("security", "none")
        stream_settings = config["outbounds"][0]["streamSettings"]

        if security == "tls":
            stream_settings["security"] = "tls"
            stream_settings["tlsSettings"] = {
                "serverName": vless_params.get("sni", vless_params["server"]),
                "allowInsecure": False,
            }

            # ALPN
            alpn = vless_params.get("alpn", "")
            if alpn:
                stream_settings["tlsSettings"]["alpn"] = alpn.split(",")

            # Fingerprint
            fp = vless_params.get("fp", "")
            if fp:
                stream_settings["tlsSettings"]["fingerprint"] = fp

        elif security == "reality":
            stream_settings["security"] = "reality"
            stream_settings["realitySettings"] = {
                "serverName": vless_params.get("sni", vless_params["server"]),
                "fingerprint": vless_params.get("fp", "chrome"),
                "show": False,
            }

            # Public Key
            pbk = vless_params.get("pbk", "")
            if pbk:
                stream_settings["realitySettings"]["publicKey"] = pbk

            # Short ID
            sid = vless_params.get("sid", "")
            if sid:
                stream_settings["realitySettings"]["shortId"] = sid

            # Spider X
            spx = vless_params.get("spx", "")
            if spx:
                stream_settings["realitySettings"]["spiderX"] = spx

        # Настройка транспорта
        network = vless_params["network"]

        if network == "ws":
            path = vless_params.get("path", "/")
            host = vless_params.get("host", "")

            stream_settings["wsSettings"] = {"path": path}
            if host:
                stream_settings["wsSettings"]["headers"] = {"Host": host}

        elif network == "grpc":
            serviceName = vless_params.get("serviceName", "")
            stream_settings["grpcSettings"] = {
                "serviceName": serviceName,
                "multiMode": False,
            }

        return config

    def start(self, vless_url):
        """
        Запуск VLESS VPN подключения

        Args:
            vless_url: VLESS URL для подключения

        Returns:
            True при успешном запуске, False при ошибке
        """
        try:
            # Проверяем наличие xray.exe или v2ray.exe
            if not self.xray_exe or not os.path.exists(self.xray_exe):
                self.log("❌ ОШИБКА: xray.exe или v2ray.exe не найден!")
                self.log("📥 Скачайте:")
                self.log("   - xray-core: https://github.com/XTLS/Xray-core/releases")
                self.log(
                    "   - v2ray-core: https://github.com/v2fly/v2ray-core/releases"
                )
                return False

            # Парсим URL
            self.log("📋 Парсинг VLESS URL...")
            vless_params = self.parse_vless_url(vless_url)
            if not vless_params:
                self.log("❌ ОШИБКА: Неверный VLESS URL")
                return False

            # Останавливаем предыдущее подключение
            if self.is_running:
                self.log("⚠ Останавливаем предыдущее подключение...")
                self.stop()

            # Генерируем конфигурацию
            self.log("⚙ Генерация конфигурации...")
            config = self.generate_xray_config(vless_params)

            # Сохраняем во временный файл
            exe_dir = get_exe_directory()

            self.config_file = os.path.join(exe_dir, "vless_config.json")

            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2, ensure_ascii=False)

            self.log(f"💾 Конфигурация сохранена: {self.config_file}")

            # Запускаем xray-core или v2ray-core
            exe_name = os.path.basename(self.xray_exe)
            self.log(f"🚀 Запуск {exe_name}...")

            # Создаём скрытый процесс
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE

            self.xray_process = subprocess.Popen(
                [self.xray_exe, "-c", self.config_file],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW,
                startupinfo=startupinfo,
            )

            # Ждём запуска (проверяем порт)
            self.log("⏳ Ожидание запуска...")
            time.sleep(2)

            if self._check_socks_port():
                self.is_running = True
                self.log("=" * 50)
                self.log("✅ VLESS VPN ПОДКЛЮЧЕН!")
                self.log(f"🔌 SOCKS5 прокси: 127.0.0.1:{self.local_socks_port}")
                self.log("=" * 50)
                return True
            else:
                self.log("❌ ОШИБКА: Не удалось запустить SOCKS5 прокси")
                self.log("   Проверьте логи и правильность VLESS URL")
                self.stop()
                return False

        except Exception as e:
            self.log("=" * 50)
            self.log(f"❌ ОШИБКА запуска VLESS: {e}")
            import traceback

            self.log(traceback.format_exc())
            self.log("=" * 50)
            self.stop()
            return False

    def stop(self):
        """Остановка VLESS VPN"""
        if not self.is_running and not self.xray_process:
            self.log("⚠ VPN уже остановлен")
            return True
        
        try:
            self.log("🛑 Остановка VPN процесса...")
            
            if self.xray_process:
                # Пробуем мягко завершить
                self.xray_process.terminate()
                
                # Ждём до 3 секунд
                try:
                    self.xray_process.wait(timeout=3)
                    self.log("✓ Процесс завершён корректно")
                except subprocess.TimeoutExpired:
                    # Если не завершился - убиваем принудительно
                    self.log("⚠ Процесс не завершился, принудительное завершение...")
                    self.xray_process.kill()
                    self.xray_process.wait()
                    self.log("✓ Процесс принудительно завершён")
            
            # Удаляем конфиг
            if self.config_file and os.path.exists(self.config_file):
                try:
                    os.remove(self.config_file)
                    self.log("🗑 Конфигурация удалена")
                except Exception as e:
                    self.log(f"⚠ Не удалось удалить конфиг: {e}")
            
            self.is_running = False
            self.xray_process = None
            self.config_file = None
            
            self.log("✅ VLESS VPN остановлен")
            return True
            
        except Exception as e:
            self.log(f"❌ ОШИБКА остановки VLESS: {e}")
            return False

    def _check_socks_port(self):
        """Проверка доступности SOCKS5 порта"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex(("127.0.0.1", self.local_socks_port))
            sock.close()
            return result == 0
        except Exception:
            return False

    def get_status(self):
        """
        Получение статуса подключения

        Returns:
            dict с информацией о статусе
        """
        status = {
            "running": self.is_running,
            "port": self.local_socks_port,
            "proxy_url": f"socks5://127.0.0.1:{self.local_socks_port}",
        }

        if self.is_running:
            # Проверяем, что порт реально доступен
            if self._check_socks_port():
                status["port_accessible"] = True
            else:
                status["port_accessible"] = False
                status["warning"] = "Процесс запущен, но порт недоступен"

        return status

    def cleanup(self):
        """Очистка при завершении программы"""
        self.log("🧹 VLESSManager: Очистка...")
        self.stop()
