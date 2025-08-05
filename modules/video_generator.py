"""
Модуль генерации видео для EKOSYSTEMA_FULL
Создает короткие видео для YouTube Shorts, TikTok, Instagram с использованием FFmpeg
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
import json

logger = logging.getLogger(__name__)

class VideoItem:
    """Элемент видеоконтента"""
    def __init__(self, video_id: str, title: str, script: str, duration: int, 
                 platform: str, video_path: str, thumbnail_path: str = None):
        self.id = video_id
        self.title = title
        self.script = script
        self.duration = duration
        self.platform = platform
        self.video_path = video_path
        self.thumbnail_path = thumbnail_path
        self.created_at = datetime.now()
        
    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "script": self.script,
            "duration": self.duration,
            "platform": self.platform,
            "video_path": self.video_path,
            "thumbnail_path": self.thumbnail_path,
            "created_at": self.created_at.isoformat()
        }

class VideoGenerator:
    """Генератор видео контента"""
    
    def __init__(self):
        self.temp_dir = Path("/tmp/ekosystema_videos")
        self.temp_dir.mkdir(exist_ok=True)
        
        # Создаем папку для медиа ресурсов
        self.media_dir = Path("/app/media")
        self.media_dir.mkdir(exist_ok=True)
        
        # Подпапки для разных типов контента
        (self.media_dir / "backgrounds").mkdir(exist_ok=True)
        (self.media_dir / "audio").mkdir(exist_ok=True)
        (self.media_dir / "fonts").mkdir(exist_ok=True)
        
        # Создаем базовые медиа ресурсы если их нет
        self._create_default_resources()
        
    def _create_default_resources(self):
        """Создает базовые медиа ресурсы для видео"""
        # Создаем простой градиентный фон
        bg_path = self.media_dir / "backgrounds" / "gradient.png"
        if not bg_path.exists():
            self._create_gradient_background(str(bg_path))
            
        # Создаем простой аудио фон (тишина)
        audio_path = self.media_dir / "audio" / "silence.mp3"
        if not audio_path.exists():
            self._create_silence_audio(str(audio_path))
    
    def _create_gradient_background(self, output_path: str):
        """Создает градиентный фон с помощью FFmpeg"""
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", "color=c=0x1e3a8a:size=1080x1920:duration=1",
            "-vf", "geq=lum='if(gte(Y,H/2),255-255*(Y-H/2)/(H/2),255-255*Y/(H/2))'",
            output_path
        ]
        subprocess.run(cmd, capture_output=True)
        logger.info(f"Создан градиентный фон: {output_path}")
    
    def _create_silence_audio(self, output_path: str, duration: int = 30):
        """Создает тихий аудио файл"""
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", f"anullsrc=channel_layout=stereo:sample_rate=48000",
            "-t", str(duration),
            "-c:a", "mp3",
            output_path
        ]
        subprocess.run(cmd, capture_output=True)
        logger.info(f"Создан аудио файл: {output_path}")
    
    async def generate_video_from_content(self, content_item: dict, platform: str = "tiktok") -> VideoItem:
        """
        Генерирует видео из текстового контента
        
        Args:
            content_item: Словарь с контентом (title, content, hashtags)
            platform: Платформа (tiktok, youtube_shorts, instagram)
        """
        video_id = str(uuid.uuid4())
        
        # Определяем параметры видео в зависимости от платформы
        video_config = self._get_platform_config(platform)
        
        # Создаем скрипт для видео
        script = self._create_video_script(content_item)
        
        # Генерируем видео
        video_path = await self._create_video(
            video_id=video_id,
            script=script,
            title=content_item.get("title", ""),
            config=video_config
        )
        
        # Создаем thumbnail
        thumbnail_path = await self._create_thumbnail(video_path, video_id)
        
        return VideoItem(
            video_id=video_id,
            title=content_item.get("title", ""),
            script=script,
            duration=video_config["duration"],
            platform=platform,
            video_path=video_path,
            thumbnail_path=thumbnail_path
        )
    
    def _get_platform_config(self, platform: str) -> dict:
        """Возвращает конфигурацию для платформы"""
        configs = {
            "tiktok": {
                "width": 1080,
                "height": 1920,
                "duration": 15,
                "fps": 30,
                "bitrate": "2M"
            },
            "youtube_shorts": {
                "width": 1080,
                "height": 1920,
                "duration": 30,
                "fps": 30,
                "bitrate": "3M"
            },
            "instagram": {
                "width": 1080,
                "height": 1920,
                "duration": 15,
                "fps": 30,
                "bitrate": "2M"
            }
        }
        return configs.get(platform, configs["tiktok"])
    
    def _create_video_script(self, content_item: dict) -> str:
        """Создает скрипт для видео из контента"""
        title = content_item.get("title", "")
        content = content_item.get("content", "")
        hashtags = content_item.get("hashtags", [])
        
        # Ограничиваем длину для короткого видео
        content_lines = content.split('\n')[:3]  # Берем первые 3 строки
        short_content = '\n'.join(content_lines)
        
        script = f"{title}\n\n{short_content}"
        
        if hashtags:
            hashtag_str = ' '.join(hashtags[:3])  # Первые 3 хештега
            script += f"\n\n{hashtag_str}"
            
        return script[:200]  # Ограничиваем до 200 символов
    
    async def _create_video(self, video_id: str, script: str, title: str, config: dict) -> str:
        """Создает видео файл с помощью FFmpeg"""
        output_path = str(self.temp_dir / f"{video_id}.mp4")
        bg_path = str(self.media_dir / "backgrounds" / "gradient.png")
        
        # Подготавливаем текст для отображения
        display_text = self._prepare_text_for_video(script, config["width"])
        
        # Команда FFmpeg для создания видео
        cmd = [
            "ffmpeg", "-y",
            "-loop", "1",
            "-i", bg_path,
            "-f", "lavfi",
            "-i", f"anullsrc=channel_layout=stereo:sample_rate=48000",
            "-vf", (
                f"scale={config['width']}:{config['height']},"
                f"drawtext=text='{display_text}':"
                f"fontcolor=white:fontsize=64:x=(w-text_w)/2:y=(h-text_h)/2:"
                f"fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
            ),
            "-c:v", "libx264",
            "-preset", "fast",
            "-b:v", config["bitrate"],
            "-c:a", "aac",
            "-b:a", "128k",
            "-t", str(config["duration"]),
            "-r", str(config["fps"]),
            "-pix_fmt", "yuv420p",
            output_path
        ]
        
        # Выполняем команду асинхронно
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            logger.error(f"FFmpeg error: {stderr.decode()}")
            raise Exception(f"Failed to create video: {stderr.decode()}")
        
        logger.info(f"Создано видео: {output_path}")
        return output_path
    
    def _prepare_text_for_video(self, text: str, width: int) -> str:
        """Подготавливает текст для отображения в видео"""
        # Заменяем специальные символы для FFmpeg
        text = text.replace("'", "\\'")
        text = text.replace(":", "\\:")
        text = text.replace(",", "\\,")
        
        # Разбиваем на строки для лучшего отображения
        words = text.split()
        lines = []
        current_line = []
        
        chars_per_line = max(20, width // 50)  # Примерно 20-40 символов на строку
        
        current_length = 0
        for word in words:
            if current_length + len(word) + 1 > chars_per_line and current_line:
                lines.append(' '.join(current_line))
                current_line = [word]
                current_length = len(word)
            else:
                current_line.append(word)
                current_length += len(word) + 1
        
        if current_line:
            lines.append(' '.join(current_line))
        
        # Ограничиваем количество строк
        return '\\n'.join(lines[:4])
    
    async def _create_thumbnail(self, video_path: str, video_id: str) -> str:
        """Создает thumbnail из видео"""
        thumbnail_path = str(self.temp_dir / f"{video_id}_thumb.jpg")
        
        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-ss", "00:00:01",
            "-vframes", "1",
            "-q:v", "2",
            thumbnail_path
        ]
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        await process.communicate()
        
        if process.returncode == 0:
            logger.info(f"Создан thumbnail: {thumbnail_path}")
            return thumbnail_path
        else:
            logger.warning(f"Не удалось создать thumbnail для {video_id}")
            return None
    
    async def generate_batch_videos(self, content_items: List[dict], platforms: List[str]) -> List[VideoItem]:
        """Генерирует видео для множества контентов и платформ"""
        videos = []
        
        for content_item in content_items:
            for platform in platforms:
                try:
                    video = await self.generate_video_from_content(content_item, platform)
                    videos.append(video)
                    logger.info(f"Создано видео {video.id} для {platform}")
                except Exception as e:
                    logger.error(f"Ошибка создания видео для {platform}: {e}")
        
        return videos
    
    def cleanup_old_videos(self, days_old: int = 7):
        """Удаляет старые временные видео файлы"""
        import time
        current_time = time.time()
        
        for file_path in self.temp_dir.glob("*"):
            if file_path.is_file():
                file_age = current_time - file_path.stat().st_mtime
                if file_age > (days_old * 24 * 3600):
                    file_path.unlink()
                    logger.info(f"Удален старый файл: {file_path}")

# Пример использования
async def main():
    generator = VideoGenerator()
    
    # Тестовый контент
    test_content = {
        "title": "Топ-5 способов заработка в Telegram",
        "content": "1. Создай свой канал\n2. Собирай подписчиков\n3. Размещай рекламу\n4. Продавай товары\n5. Используй ботов",
        "hashtags": ["#telegram", "#заработок", "#деньги"]
    }
    
    # Генерируем видео
    video = await generator.generate_video_from_content(test_content, "tiktok")
    print(f"Создано видео: {video.video_path}")

if __name__ == "__main__":
    asyncio.run(main())