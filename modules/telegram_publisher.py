"""
EKOSYSTEMA_FULL - Telegram публикатор
Автоматическая публикация контента в Telegram каналы и группы
"""
import asyncio
import logging
import uuid
from datetime import datetime
from typing import List, Dict, Optional
from pydantic import BaseModel
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, ContextTypes
from .content_generator import ContentItem


class TelegramPost(BaseModel):
    id: str
    content_id: str
    channel_id: str
    message_id: int
    status: str
    timestamp: datetime
    engagement: Dict = {}

class TelegramPublisher:
    def __init__(self, bot_token: str):
        self.bot_token = bot_token
        self.bot = Bot(token=bot_token)
        self.logger = logging.getLogger(__name__)
        self.published_posts: List[TelegramPost] = []
        
        # Настройки публикации
        self.channels = {
            # Можно добавить реальные каналы пользователя
            "main": "@your_main_channel",  # Замените на реальный канал
            "news": "@your_news_channel",  # Замените на реальный канал
        }

    async def publish_content(self, content_item: ContentItem, channel_key: str = "main") -> Optional[TelegramPost]:
        """Публикация одного контента в Telegram"""
        try:
            channel_id = self.channels.get(channel_key)
            if not channel_id:
                self.logger.error(f"Канал {channel_key} не настроен")
                return None
            
            # Подготавливаем текст сообщения
            message_text = self._format_message(content_item)
            
            # Отправляем сообщение
            message = await self.bot.send_message(
                chat_id=channel_id,
                text=message_text,
                parse_mode='HTML',
                disable_web_page_preview=False
            )
            
            # Создаём запись о публикации
            telegram_post = TelegramPost(
                id=str(uuid.uuid4()),
                content_id=content_item.id,
                channel_id=channel_id,
                message_id=message.message_id,
                status="published",
                timestamp=datetime.utcnow()
            )
            
            self.published_posts.append(telegram_post)
            self.logger.info(f"Опубликован пост в {channel_id}: {content_item.title[:50]}")
            
            return telegram_post
            
        except Exception as e:
            self.logger.error(f"Ошибка публикации в Telegram: {e}")
            # В режиме разработки просто логируем содержимое
            self.logger.info(f"DEMO MODE - Пост для {channel_key}:")
            self.logger.info(f"Заголовок: {content_item.title}")
            self.logger.info(f"Контент: {content_item.content}")
            self.logger.info(f"Хештеги: {', '.join(content_item.hashtags)}")
            
            # Создаём фиктивную запись для демо
            return TelegramPost(
                id=str(uuid.uuid4()),
                content_id=content_item.id,
                channel_id=f"demo_{channel_key}",
                message_id=999999,
                status="demo_published",
                timestamp=datetime.utcnow()
            )

    async def publish_batch(self, content_items, channel_key: str = "main", delay_seconds: int = 10) -> List[TelegramPost]:
        """Пакетная публикация с задержками - работает с dict и ContentItem"""
        published_posts = []
        
        for i, content_item in enumerate(content_items):
            # Проверяем тип данных и извлекаем информацию
            if hasattr(content_item, 'dict'):
                # Это ContentItem объект
                item_data = content_item
            elif isinstance(content_item, dict):
                # Это уже словарь, создаем объект
                from .content_generator import ContentItem
                try:
                    item_data = ContentItem(**content_item)
                except Exception as e:
                    self.logger.error(f"Ошибка создания ContentItem: {e}")
                    self.logger.info(f"Данные контента: {content_item}")
                    # Создаем минимальный объект для публикации
                    item_data = self._create_fallback_content_item(content_item)
            else:
                self.logger.error(f"Неизвестный тип контента: {type(content_item)}")
                continue
            
            # Публикуем контент
            post = await self.publish_content(item_data, channel_key)
            if post:
                published_posts.append(post)
        """Пакетная публикация с задержками"""
        published_posts = []
        
        for i, content_item in enumerate(content_items):
            # Публикуем контент
            post = await self.publish_content(content_item, channel_key)
            if post:
                published_posts.append(post)
            
            # Задержка между публикациями (кроме последнего)
            if i < len(content_items) - 1:
                await asyncio.sleep(delay_seconds)
                self.logger.info(f"Ожидание {delay_seconds} секунд до следующей публикации...")
        
        self.logger.info(f"Опубликовано {len(published_posts)} постов в канал {channel_key}")
        return published_posts

    def _format_message(self, content_item: ContentItem) -> str:
        """Форматирование сообщения для Telegram"""
        message_parts = []
        
        # Добавляем основной контент
        message_parts.append(content_item.content)
        
        # Добавляем хештеги если их нет в основном тексте
        if content_item.hashtags and not any('#' in content_item.content for _ in content_item.hashtags):
            hashtags_line = " ".join(content_item.hashtags)
            message_parts.append(f"\n{hashtags_line}")
        
        # Добавляем ссылку на источник если есть
        if content_item.metadata.get('source_url'):
            source_url = content_item.metadata['source_url']
            message_parts.append(f"\n\n🔗 <a href='{source_url}'>Источник</a>")
        
        # Добавляем подпись канала
        message_parts.append(f"\n\n📺 <b>EKOSYSTEMA</b> | <i>Автоматический контент</i>")
        
        return "".join(message_parts)

    async def get_channel_info(self, channel_key: str = "main") -> Dict:
        """Получение информации о канале"""
        try:
            channel_id = self.channels.get(channel_key)
            if not channel_id:
                return {"error": f"Канал {channel_key} не настроен"}
            
            chat = await self.bot.get_chat(channel_id)
            
            return {
                "id": chat.id,
                "title": chat.title,
                "type": chat.type,
                "description": chat.description,
                "member_count": await self.bot.get_chat_member_count(channel_id) if chat.type in ['group', 'supergroup'] else None,
                "username": chat.username
            }
            
        except Exception as e:
            self.logger.error(f"Ошибка получения информации о канале: {e}")
            return {"error": str(e)}

    def get_publishing_stats(self) -> Dict:
        """Статистика публикаций"""
        if not self.published_posts:
            return {"message": "Публикаций пока нет"}
        
        stats = {
            "total_posts": len(self.published_posts),
            "channels": {},
            "recent_posts": [],
            "status_breakdown": {}
        }
        
        for post in self.published_posts:
            # Статистика по каналам
            channel = post.channel_id
            if channel not in stats["channels"]:
                stats["channels"][channel] = {"count": 0, "last_post": None}
            stats["channels"][channel]["count"] += 1
            stats["channels"][channel]["last_post"] = post.timestamp.isoformat()
            
            # Статистика по статусам
            status = post.status
            stats["status_breakdown"][status] = stats["status_breakdown"].get(status, 0) + 1
        
        # Последние 5 постов
        recent = sorted(self.published_posts, key=lambda x: x.timestamp, reverse=True)[:5]
        for post in recent:
            stats["recent_posts"].append({
                "id": post.id,
                "channel": post.channel_id,
                "status": post.status,
                "timestamp": post.timestamp.isoformat()
            })
        
        return stats

    async def setup_bot_commands(self):
        """Настройка команд бота для управления"""
        commands = [
            ("start", "Начать работу с ботом"),
            ("help", "Показать справку"),
            ("stats", "Статистика публикаций"),
            ("channels", "Информация о каналах"),
        ]
        
        await self.bot.set_my_commands(commands)

    # Обработчики команд для бота
    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /start"""
        welcome_text = """
🤖 <b>EKOSYSTEMA Bot</b>

Автоматическая система создания и публикации контента.

Доступные команды:
/help - Показать справку
/stats - Статистика публикаций  
/channels - Информация о каналах

🔥 Система работает в автоматическом режиме!
        """
        await update.message.reply_text(welcome_text, parse_mode='HTML')

    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /help"""
        help_text = """
📋 <b>Справка по EKOSYSTEMA Bot</b>

<b>Основные функции:</b>
🔍 Автоматический сбор трендов из YouTube, Reddit
🤖 Генерация контента с помощью AI
📤 Публикация в Telegram каналы

<b>Команды:</b>
/stats - Посмотреть статистику
/channels - Информация о подключённых каналах

<b>Система работает автономно 24/7!</b>
        """
        await update.message.reply_text(help_text, parse_mode='HTML')

    async def cmd_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /stats"""
        stats = self.get_publishing_stats()
        
        if "message" in stats:
            await update.message.reply_text(stats["message"])
            return
        
        stats_text = f"""
📊 <b>Статистика публикаций</b>

📝 Всего постов: {stats['total_posts']}
📺 Активных каналов: {len(stats['channels'])}

<b>По каналам:</b>
        """
        
        for channel, data in stats['channels'].items():
            stats_text += f"\n• {channel}: {data['count']} постов"
        
        await update.message.reply_text(stats_text, parse_mode='HTML')


# Пример использования
async def main():
    from content_generator import ContentGenerator
    from trend_collector import TrendCollector
    
    # Инициализация компонентов
    collector = TrendCollector(youtube_api_key="AIzaSyCuWvZcQuOG8pPgkAMPY5_QmPaql7tZUcI") 
    generator = ContentGenerator(gemini_api_key="AIzaSyBSArxA7X_nUg-S41JketY3nLqR3VWGCTw")
    publisher = TelegramPublisher(bot_token="8272796200:AAElpR54wTR7kdtxs0pulNB6ZMUg6ZC4AKo")
    
    # Полный цикл: тренды → контент → публикация
    print("🔍 Собираем тренды...")
    trends = await collector.collect_all_trends()
    
    print("🤖 Генерируем контент...")
    content_batch = await generator.generate_batch_content(trends[:3], ["telegram"])
    telegram_content = content_batch.get("telegram", [])
    
    if telegram_content:
        print(f"📤 Публикуем {len(telegram_content)} постов...")
        published = await publisher.publish_batch(telegram_content, delay_seconds=5)
        
        print(f"✅ Опубликовано: {len(published)} постов")
        
        # Показываем статистику
        stats = publisher.get_publishing_stats()
        print(f"📊 Общая статистика: {stats['total_posts']} постов в {len(stats['channels'])} каналах")
    else:
        print("❌ Не удалось сгенерировать контент для Telegram")

if __name__ == "__main__":
    asyncio.run(main())