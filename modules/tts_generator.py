"""
Модуль TTS (Text-to-Speech) для EKOSYSTEMA_FULL
Генерирует голосовое сопровождение для видео
"""

import os
import subprocess
import uuid
import asyncio
import logging
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
import tempfile

logger = logging.getLogger(__name__)

class TTSGenerator:
    """Генератор речи из текста"""
    
    def __init__(self):
        self.temp_dir = Path("/tmp/ekosystema_audio")
        self.temp_dir.mkdir(exist_ok=True)
        
        # Проверяем доступность TTS движков
        self.available_engines = self._check_available_engines()
        
    def _check_available_engines(self) -> List[str]:
        """Проверяет доступные TTS движки"""
        engines = []
        
        # Проверяем espeak (базовый TTS)
        try:
            subprocess.run(["espeak", "--version"], capture_output=True, check=True)
            engines.append("espeak")
            logger.info("Найден TTS движок: espeak")
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass
            
        # Проверяем festival
        try:
            subprocess.run(["festival", "--version"], capture_output=True, check=True)
            engines.append("festival")
            logger.info("Найден TTS движок: festival")
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass
            
        if not engines:
            logger.warning("TTS движки не найдены, будет установлен espeak")
            self._install_espeak()
            engines.append("espeak")
            
        return engines
    
    def _install_espeak(self):
        """Устанавливает espeak TTS движок"""
        try:
            subprocess.run(["apt", "update"], check=True)
            subprocess.run(["apt", "install", "-y", "espeak", "espeak-data"], check=True)
            logger.info("Установлен espeak TTS движок")
        except subprocess.CalledProcessError as e:
            logger.error(f"Ошибка установки espeak: {e}")
    
    async def text_to_speech(self, text: str, voice: str = "ru", speed: int = 150) -> str:
        """
        Конвертирует текст в речь
        
        Args:
            text: Текст для озвучки
            voice: Голос (ru, en, de и т.д.)
            speed: Скорость речи (слов в минуту)
            
        Returns:
            Путь к аудио файлу
        """
        audio_id = str(uuid.uuid4())
        output_path = str(self.temp_dir / f"{audio_id}.wav")
        
        if "espeak" in self.available_engines:
            return await self._espeak_tts(text, output_path, voice, speed)
        elif "festival" in self.available_engines:
            return await self._festival_tts(text, output_path)
        else:
            # Fallback: создаем тишину
            return await self._create_silence(output_path, len(text) // 10)
    
    async def _espeak_tts(self, text: str, output_path: str, voice: str, speed: int) -> str:
        """Генерирует речь с помощью espeak"""
        # Подготавливаем текст
        clean_text = self._clean_text_for_tts(text)
        
        cmd = [
            "espeak",
            "-v", voice,
            "-s", str(speed),
            "-w", output_path,
            clean_text
        ]
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            logger.error(f"Espeak error: {stderr.decode()}")
            # Создаем тишину как fallback
            return await self._create_silence(output_path, len(text) // 10)
        
        # Конвертируем в MP3 для лучшего сжатия
        mp3_path = output_path.replace(".wav", ".mp3")
        await self._convert_to_mp3(output_path, mp3_path)
        
        logger.info(f"Создана озвучка: {mp3_path}")
        return mp3_path
    
    async def _festival_tts(self, text: str, output_path: str) -> str:
        """Генерирует речь с помощью festival"""
        clean_text = self._clean_text_for_tts(text)
        
        # Создаем временный текстовый файл
        text_file = str(self.temp_dir / f"temp_{uuid.uuid4()}.txt")
        with open(text_file, 'w', encoding='utf-8') as f:
            f.write(clean_text)
        
        cmd = [
            "festival",
            "--tts",
            text_file,
            "--otype", "wav",
            "--output", output_path
        ]
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        await process.communicate()
        
        # Удаляем временный файл
        os.unlink(text_file)
        
        if process.returncode == 0:
            mp3_path = output_path.replace(".wav", ".mp3")
            await self._convert_to_mp3(output_path, mp3_path)
            return mp3_path
        else:
            return await self._create_silence(output_path, len(text) // 10)
    
    def _clean_text_for_tts(self, text: str) -> str:
        """Очищает текст для TTS"""
        # Удаляем специальные символы
        clean_text = text.replace("#", "хештег ")
        clean_text = clean_text.replace("@", "собака ")
        clean_text = clean_text.replace("&", " и ")
        clean_text = clean_text.replace("%", " процентов")
        
        # Заменяем переносы строк на паузы
        clean_text = clean_text.replace("\n", ". ")
        
        # Ограничиваем длину
        if len(clean_text) > 500:
            clean_text = clean_text[:500] + "..."
            
        return clean_text
    
    async def _convert_to_mp3(self, wav_path: str, mp3_path: str):
        """Конвертирует WAV в MP3"""
        cmd = [
            "ffmpeg", "-y",
            "-i", wav_path,
            "-codec:a", "mp3",
            "-b:a", "128k",
            mp3_path
        ]
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        await process.communicate()
        
        # Удаляем оригинальный WAV файл
        if os.path.exists(wav_path):
            os.unlink(wav_path)
    
    async def _create_silence(self, output_path: str, duration_seconds: int) -> str:
        """Создает тишину как fallback"""
        mp3_path = output_path.replace(".wav", ".mp3")
        
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
            "-t", str(max(5, min(30, duration_seconds))),
            "-c:a", "mp3",
            mp3_path
        ]
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        await process.communicate()
        return mp3_path
    
    async def generate_batch_audio(self, texts: List[str], voice: str = "ru") -> List[str]:
        """Генерирует аудио для множества текстов"""
        audio_files = []
        
        for text in texts:
            try:
                audio_path = await self.text_to_speech(text, voice)
                audio_files.append(audio_path)
                logger.info(f"Создан аудио файл: {audio_path}")
            except Exception as e:
                logger.error(f"Ошибка создания аудио для текста '{text[:50]}...': {e}")
        
        return audio_files
    
    def cleanup_old_audio(self, days_old: int = 7):
        """Удаляет старые аудио файлы"""
        import time
        current_time = time.time()
        
        for file_path in self.temp_dir.glob("*"):
            if file_path.is_file():
                file_age = current_time - file_path.stat().st_mtime
                if file_age > (days_old * 24 * 3600):
                    file_path.unlink()
                    logger.info(f"Удален старый аудио файл: {file_path}")

# Пример использования
async def main():
    tts = TTSGenerator()
    
    test_text = "Привет! Это тест системы озвучки для видео контента. Сегодня мы поговорим о заработке в телеграм."
    
    audio_path = await tts.text_to_speech(test_text, voice="ru", speed=160)
    print(f"Создан аудио файл: {audio_path}")

if __name__ == "__main__":
    asyncio.run(main())