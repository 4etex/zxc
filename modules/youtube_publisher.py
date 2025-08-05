"""
YouTube Shorts Publisher для EKOSYSTEMA_FULL
Публикует короткие видео на YouTube через YouTube Data API
"""

import os
import logging
from typing import List, Dict, Optional
from pathlib import Path
import asyncio
from datetime import datetime

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

logger = logging.getLogger(__name__)

class YouTubePublisher:
    """Публикатор для YouTube Shorts"""
    
    SCOPES = ['https://www.googleapis.com/auth/youtube.upload']
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key
        self.service = None
        self.credentials_path = "/app/credentials/youtube_credentials.json"
        self.token_path = "/app/credentials/youtube_token.json"
        
        # Создаем папку для учетных данных
        Path(self.credentials_path).parent.mkdir(exist_ok=True)
        
    async def authenticate(self) -> bool:
        """Аутентификация в YouTube API"""
        try:
            creds = None
            
            # Проверяем существующий токен
            if os.path.exists(self.token_path):
                creds = Credentials.from_authorized_user_file(self.token_path, self.SCOPES)
            
            # Если токен недействителен, обновляем
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    # Нужна первичная авторизация
                    if not os.path.exists(self.credentials_path):
                        logger.warning("YouTube credentials file not found. Using API key only mode.")
                        return False
                    
                    flow = InstalledAppFlow.from_client_secrets_file(
                        self.credentials_path, self.SCOPES)
                    creds = flow.run_local_server(port=0)
                
                # Сохраняем токен
                with open(self.token_path, 'w') as token:
                    token.write(creds.to_json())
            
            # Создаем сервис
            self.service = build('youtube', 'v3', credentials=creds)
            logger.info("YouTube API аутентификация успешна")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка аутентификации YouTube: {e}")
            return False
    
    async def upload_video(self, video_path: str, title: str, description: str = "", 
                          tags: List[str] = None, category_id: str = "22") -> Optional[str]:
        """
        Загружает видео на YouTube
        
        Args:
            video_path: Путь к видео файлу
            title: Заголовок видео
            description: Описание видео
            tags: Теги видео
            category_id: ID категории (22 = People & Blogs)
            
        Returns:
            ID загруженного видео или None при ошибке
        """
        if not self.service:
            if not await self.authenticate():
                logger.error("Не удалось аутентифицироваться в YouTube")
                return None
        
        if not os.path.exists(video_path):
            logger.error(f"Видео файл не найден: {video_path}")
            return None
        
        try:
            # Подготавливаем метаданные
            body = {
                'snippet': {
                    'title': title[:100],  # YouTube limit
                    'description': self._format_description(description, tags),
                    'tags': tags[:10] if tags else [],  # Max 10 tags
                    'categoryId': category_id
                },
                'status': {
                    'privacyStatus': 'public',  # или 'private', 'unlisted'
                    'selfDeclaredMadeForKids': False
                }
            }
            
            # Добавляем указание что это Shorts (для вертикальных видео)
            if self._is_shorts_format(video_path):
                body['snippet']['description'] += "\n\n#Shorts"
            
            # Загружаем файл
            media = MediaFileUpload(
                video_path,
                chunksize=-1,
                resumable=True,
                mimetype="video/mp4"
            )
            
            # Выполняем загрузку
            request = self.service.videos().insert(
                part=','.join(body.keys()),
                body=body,
                media_body=media
            )
            
            response = None
            error = None
            retry = 0
            
            while response is None:
                try:
                    status, response = request.next_chunk()
                    if status:
                        logger.info(f"Загрузка {int(status.progress() * 100)}%")
                except Exception as e:
                    error = e
                    retry += 1
                    if retry > 3:
                        break
                    await asyncio.sleep(2 ** retry)
            
            if response:
                video_id = response.get('id')
                logger.info(f"Видео успешно загружено на YouTube: {video_id}")
                return video_id
            else:
                logger.error(f"Ошибка загрузки видео на YouTube: {error}")
                return None
                
        except Exception as e:
            logger.error(f"Ошибка публикации на YouTube: {e}")
            return None
    
    def _format_description(self, description: str, tags: List[str] = None) -> str:
        """Форматирует описание для YouTube"""
        formatted_desc = description[:5000]  # YouTube limit
        
        if tags:
            # Добавляем хештеги в описание
            hashtags = [f"#{tag.replace('#', '').replace(' ', '')}" for tag in tags[:3]]
            formatted_desc += f"\n\n{' '.join(hashtags)}"
        
        # Добавляем промо текст
        formatted_desc += "\n\n🔔 Подпишитесь на канал для новых видео!"
        formatted_desc += "\n💬 Пишите в комментариях ваши вопросы!"
        
        return formatted_desc
    
    def _is_shorts_format(self, video_path: str) -> bool:
        """Проверяет, является ли видео форматом Shorts (вертикальное)"""
        try:
            import subprocess
            cmd = [
                "ffprobe", "-v", "quiet", "-print_format", "json",
                "-show_streams", video_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                import json
                data = json.loads(result.stdout)
                
                for stream in data.get('streams', []):
                    if stream.get('codec_type') == 'video':
                        width = stream.get('width', 0)
                        height = stream.get('height', 0)
                        
                        # YouTube Shorts: вертикальное видео (высота > ширины)
                        return height > width
            
            return False
        except Exception:
            return False
    
    async def upload_batch_videos(self, videos_info: List[Dict]) -> List[Optional[str]]:
        """Загружает множество видео"""
        video_ids = []
        
        for video_info in videos_info:
            try:
                video_id = await self.upload_video(
                    video_path=video_info.get('video_path'),
                    title=video_info.get('title', 'YouTube Short'),
                    description=video_info.get('script', ''),
                    tags=video_info.get('hashtags', [])
                )
                video_ids.append(video_id)
                
                # Пауза между загрузками
                await asyncio.sleep(10)
                
            except Exception as e:
                logger.error(f"Ошибка загрузки видео {video_info.get('title', '')}: {e}")
                video_ids.append(None)
        
        return video_ids
    
    async def get_channel_info(self) -> Optional[Dict]:
        """Получает информацию о канале"""
        if not self.service:
            if not await self.authenticate():
                return None
        
        try:
            request = self.service.channels().list(
                part='snippet,statistics',
                mine=True
            )
            response = request.execute()
            
            if response.get('items'):
                channel = response['items'][0]
                return {
                    'id': channel.get('id'),
                    'title': channel['snippet'].get('title'),
                    'subscribers': channel['statistics'].get('subscriberCount', '0'),
                    'videos': channel['statistics'].get('videoCount', '0'),
                    'views': channel['statistics'].get('viewCount', '0')
                }
        except Exception as e:
            logger.error(f"Ошибка получения информации о канале: {e}")
        
        return None
    
    def create_credentials_template(self) -> str:
        """Создает шаблон файла учетных данных"""
        template = {
            "installed": {
                "client_id": "YOUR_CLIENT_ID.apps.googleusercontent.com",
                "project_id": "your-project-id",
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                "client_secret": "YOUR_CLIENT_SECRET",
                "redirect_uris": ["http://localhost"]
            }
        }
        
        import json
        with open(self.credentials_path, 'w') as f:
            json.dump(template, f, indent=2)
        
        return self.credentials_path

# Пример использования
async def main():
    publisher = YouTubePublisher()
    
    # Пример загрузки видео
    video_info = {
        'video_path': '/path/to/video.mp4',
        'title': 'Тест YouTube Shorts',
        'script': 'Это тестовое видео для проверки загрузки на YouTube',
        'hashtags': ['#test', '#shorts', '#youtube']
    }
    
    if await publisher.authenticate():
        video_id = await publisher.upload_video(
            video_info['video_path'],
            video_info['title'],
            video_info['script'],
            video_info['hashtags']
        )
        print(f"Загружено видео: {video_id}")
    else:
        print("Ошибка аутентификации")

if __name__ == "__main__":
    asyncio.run(main())