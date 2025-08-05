"""
Модуль расширенной генерации видео с озвучкой для EKOSYSTEMA_FULL
Создает полноценные видео с текстом, озвучкой и визуальными эффектами
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

from .video_generator import VideoGenerator, VideoItem
from .tts_generator import TTSGenerator

logger = logging.getLogger(__name__)

class EnhancedVideoGenerator:
    """Расширенный генератор видео с озвучкой и эффектами"""
    
    def __init__(self):
        self.video_gen = VideoGenerator()
        self.tts_gen = TTSGenerator()
        self.temp_dir = Path("/tmp/ekosystema_enhanced")
        self.temp_dir.mkdir(exist_ok=True)
        
    async def create_full_video(self, content_item: dict, platform: str = "tiktok", 
                               with_voice: bool = True, voice_lang: str = "ru") -> VideoItem:
        """
        Создает полноценное видео с текстом и озвучкой
        
        Args:
            content_item: Контент для видео
            platform: Платформа
            with_voice: Добавлять ли озвучку
            voice_lang: Язык озвучки
        """
        video_id = str(uuid.uuid4())
        config = self.video_gen._get_platform_config(platform)
        
        # Создаем скрипт
        script = self.video_gen._create_video_script(content_item)
        
        # Генерируем озвучку если нужно  
        audio_path = None
        if with_voice:
            try:
                audio_path = await self.tts_gen.text_to_speech(script, voice_lang)
                logger.info(f"Создан аудио: {audio_path}")
            except Exception as e:
                logger.warning(f"Ошибка создания озвучки: {e}")
        
        # Создаем видео с улучшенными эффектами
        video_path = await self._create_enhanced_video(
            video_id=video_id,
            script=script,
            title=content_item.get("title", ""),
            config=config,
            audio_path=audio_path
        )
        
        # Создаем thumbnail
        thumbnail_path = await self.video_gen._create_thumbnail(video_path, video_id)
        
        return VideoItem(
            video_id=video_id,
            title=content_item.get("title", ""),
            script=script,
            duration=config["duration"],
            platform=platform,
            video_path=video_path,
            thumbnail_path=thumbnail_path
        )
    
    async def _create_enhanced_video(self, video_id: str, script: str, title: str, 
                                   config: dict, audio_path: str = None) -> str:
        """Создает улучшенное видео с эффектами"""
        output_path = str(self.temp_dir / f"{video_id}.mp4")
        
        # Создаем анимированный фон
        bg_path = await self._create_animated_background(video_id, config)
        
        # Подготавливаем текст
        display_text = self.video_gen._prepare_text_for_video(script, config["width"])
        
        # Базовая команда FFmpeg
        cmd = ["ffmpeg", "-y"]
        
        # Входные файлы
        cmd.extend(["-i", bg_path])  # Фон
        
        if audio_path and os.path.exists(audio_path):
            cmd.extend(["-i", audio_path])  # Аудио
        else:
            # Создаем тишину
            cmd.extend(["-f", "lavfi", "-i", f"anullsrc=channel_layout=stereo:sample_rate=48000"])
        
        # Видео фильтры с анимацией текста
        video_filters = [
            f"scale={config['width']}:{config['height']}",
            # Анимация появления текста
            f"drawtext=text='{display_text}':"
            f"fontcolor=white:fontsize=72:x=(w-text_w)/2:y=(h-text_h)/2:"
            f"fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
            f"alpha='if(lt(t,1),t/1,if(lt(t,{config['duration']-1}),1,(({config['duration']}-t)/1)))'",
            # Добавляем легкий эффект пульсации
            f"scale='if(lt(t,2),iw*(0.95+0.05*sin(2*PI*t*2)),iw)':'if(lt(t,2),ih*(0.95+0.05*sin(2*PI*t*2)),ih)'"
        ]
        
        cmd.extend(["-vf", ",".join(video_filters)])
        
        # Кодеки и параметры
        cmd.extend([
            "-c:v", "libx264",
            "-preset", "medium",  # Лучше качество чем fast
            "-b:v", config["bitrate"],
            "-c:a", "aac",
            "-b:a", "128k",
            "-t", str(config["duration"]),
            "-r", str(config["fps"]),
            "-pix_fmt", "yuv420p"
        ])
        
        # Если есть аудио, синхронизируем
        if audio_path and os.path.exists(audio_path):
            cmd.extend(["-map", "0:v", "-map", "1:a"])
        
        cmd.append(output_path)
        
        # Выполняем команду
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            logger.error(f"FFmpeg enhanced video error: {stderr.decode()}")
            # Fallback к простому видео
            return await self.video_gen._create_video(video_id, script, title, config)
        
        logger.info(f"Создано улучшенное видео: {output_path}")
        return output_path
    
    async def _create_animated_background(self, video_id: str, config: dict) -> str:
        """Создает анимированный фон"""
        bg_path = str(self.temp_dir / f"{video_id}_bg.mp4")
        
        # Создаем анимированный градиент
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", (
                f"color=c=0x1e3a8a:size={config['width']}x{config['height']},"
                f"geq=lum='128+127*sin(2*PI*t*0.1+Y*0.01)':cb=128:cr=128"
            ),
            "-t", str(config["duration"]),
            "-r", str(config["fps"]),
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-pix_fmt", "yuv420p",
            bg_path
        ]
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            logger.warning(f"Не удалось создать анимированный фон: {stderr.decode()}")
            # Fallback к статичному фону
            return str(self.video_gen.media_dir / "backgrounds" / "gradient.png")
        
        return bg_path
    
    async def generate_video_series(self, content_items: List[dict], 
                                  platform: str = "tiktok", 
                                  with_voice: bool = True) -> List[VideoItem]:
        """Генерирует серию связанных видео"""
        videos = []
        
        for i, content_item in enumerate(content_items):
            try:
                # Добавляем номер серии в заголовок
                enhanced_content = content_item.copy()
                if len(content_items) > 1:
                    enhanced_content["title"] = f"#{i+1} {enhanced_content.get('title', '')}"
                
                video = await self.create_full_video(
                    enhanced_content, 
                    platform, 
                    with_voice,
                    voice_lang="ru"
                )
                videos.append(video)
                
                logger.info(f"Создано видео #{i+1}: {video.video_path}")
                
                # Небольшая пауза между генерациями
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"Ошибка создания видео #{i+1}: {e}")
        
        return videos
    
    async def create_compilation_video(self, videos: List[VideoItem], 
                                     title: str = "Compilation") -> VideoItem:
        """Создает компиляцию из нескольких видео"""
        compilation_id = str(uuid.uuid4())
        output_path = str(self.temp_dir / f"{compilation_id}_compilation.mp4")
        
        if not videos:
            raise ValueError("Нет видео для компиляции")
        
        # Создаем список файлов для конкатенации
        concat_file = str(self.temp_dir / f"{compilation_id}_list.txt")
        with open(concat_file, 'w') as f:
            for video in videos:
                f.write(f"file '{video.video_path}'\n")
        
        # Создаем компиляцию
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", concat_file,
            "-c:v", "libx264",
            "-c:a", "aac",
            "-preset", "medium",
            output_path
        ]
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        # Удаляем временный файл
        os.unlink(concat_file)
        
        if process.returncode != 0:
            logger.error(f"Ошибка создания компиляции: {stderr.decode()}")
            raise Exception("Не удалось создать компиляцию")
        
        # Создаем thumbnail
        thumbnail_path = await self.video_gen._create_thumbnail(output_path, compilation_id)
        
        total_duration = sum(video.duration for video in videos)
        
        return VideoItem(
            video_id=compilation_id,
            title=title,
            script=f"Компиляция из {len(videos)} видео",
            duration=total_duration,
            platform=videos[0].platform if videos else "tiktok",
            video_path=output_path,
            thumbnail_path=thumbnail_path
        )
    
    def cleanup_temp_files(self):
        """Очищает временные файлы"""
        self.video_gen.cleanup_old_videos()
        self.tts_gen.cleanup_old_audio()
        
        # Очищаем свои временные файлы
        for file_path in self.temp_dir.glob("*"):
            if file_path.is_file():
                try:
                    file_path.unlink()
                    logger.info(f"Удален временный файл: {file_path}")
                except Exception as e:
                    logger.warning(f"Не удалось удалить {file_path}: {e}")

# Пример использования
async def main():
    enhanced_gen = EnhancedVideoGenerator()
    
    # Тестовый контент
    test_content = {
        "title": "Как заработать в Telegram за 5 минут",
        "content": "Сегодня я покажу вам простой способ заработка в телеграм. Всего за 5 минут настройки вы сможете получать пассивный доход.",
        "hashtags": ["#telegram", "#заработок", "#деньги", "#лайфхак"]
    }
    
    # Создаем улучшенное видео с озвучкой
    video = await enhanced_gen.create_full_video(test_content, "tiktok", with_voice=True)
    print(f"Создано видео: {video.video_path}")
    print(f"Thumbnail: {video.thumbnail_path}")

if __name__ == "__main__":
    asyncio.run(main())