"""
EKOSYSTEMA_FULL - Генератор контента
LLM-powered генерация контента для различных платформ:
- Посты для Telegram
- Сценарии для YouTube Shorts  
- Тексты для TikTok
- Instagram описания
"""
import asyncio
import json
import uuid
import logging
from datetime import datetime
from typing import List, Dict, Optional
from pydantic import BaseModel
import google.generativeai as genai
from .trend_collector import TrendItem


class ContentItem(BaseModel):
    id: str
    trend_id: str
    platform: str
    content_type: str
    title: str
    content: str
    hashtags: List[str]
    keywords: List[str]
    timestamp: datetime
    metadata: Dict = {}

class ContentGenerator:
    def __init__(self, gemini_api_key: str):
        self.gemini_api_key = gemini_api_key
        self.logger = logging.getLogger(__name__)
        
        # Configure Gemini
        genai.configure(api_key=gemini_api_key)
        self.model = genai.GenerativeModel('gemini-1.5-flash')
        
        # Промпты для различных платформ
        self.prompts = {
            "telegram": """Создай увлекательный пост для Telegram канала на основе тренда: "{title}"
            
Требования:
- Длина: 150-300 слов  
- Стиль: информативный, но живой
- Добавь эмодзи для привлекательности
- Включи призыв к действию
- Сделай контент вирусным и интересным

Тренд: {description}
URL источника: {url}

Создай только текст поста, без лишних комментариев.""",

            "youtube_shorts": """Создай сценарий для YouTube Shorts видео длительностью 60 секунд на тему: "{title}"

Требования:
- Длительность: 60 секунд (примерно 150-200 слов)
- Структура: Хук (5 сек) → Основной контент (45 сек) → Призыв к действию (10 сек)
- Стиль: динамичный, захватывающий
- Добавь визуальные подсказки в скобках [ПОКАЗАТЬ: ...]
- Сделай контент максимально вирусным

Исходная информация: {description}
URL: {url}

Создай только сценарий, без лишних комментариев.""",

            "tiktok": """Создай текст для TikTok видео на тему: "{title}"

Требования:
- Длина: 50-100 слов
- Стиль: молодёжный, трендовый
- Много эмодзи
- Хештеги в конце
- Сделай максимально цепляющим для молодой аудитории

Информация: {description}
URL: {url}

Создай только текст, без комментариев.""",

            "instagram": """Создай описание для Instagram поста на тему: "{title}"

Требования:
- Длина: 100-200 слов
- Стиль: визуально привлекательный
- Включи релевантные хештеги
- Добавь эмодзи
- Призыв к взаимодействию (лайки, комментарии)

Контекст: {description}
URL: {url}

Создай только описание поста."""
        }

    async def generate_content_for_trend(self, trend: TrendItem, platform: str) -> ContentItem:
        """Генерация контента для конкретного тренда и платформы"""
        try:
            # Формируем промпт для платформы
            prompt_template = self.prompts.get(platform, self.prompts["telegram"])
            prompt = prompt_template.format(
                title=trend.title,
                description=trend.description or "Популярная тема в интернете",
                url=trend.url
            )
            
            # Генерируем контент через Gemini
            response = await asyncio.to_thread(self.model.generate_content, prompt)
            generated_content = response.text
            
            # Извлекаем хештеги из сгенерированного контента
            hashtags = self._extract_hashtags(generated_content, platform)
            
            content_item = ContentItem(
                id=str(uuid.uuid4()),
                trend_id=trend.id,
                platform=platform,
                content_type="text",
                title=trend.title[:100],  # Ограничиваем длину заголовка
                content=generated_content,
                hashtags=hashtags,
                keywords=trend.keywords,
                timestamp=datetime.utcnow(),
                metadata={
                    "source_url": trend.url,
                    "source_platform": trend.source,
                    "popularity_score": trend.popularity_score,
                    "trend_category": trend.category
                }
            )
            
            self.logger.info(f"Создан контент для {platform}: {trend.title[:50]}...")
            return content_item
            
        except Exception as e:
            self.logger.error(f"Ошибка генерации контента для {platform}: {e}")
            # Возвращаем базовый контент в случае ошибки
            return self._create_fallback_content(trend, platform)

    async def generate_batch_content(self, trends: List[TrendItem], platforms: List[str]) -> Dict[str, List[ContentItem]]:
        """Массовая генерация контента для нескольких трендов и платформ"""
        content_batch = {platform: [] for platform in platforms}
        
        # Ограничиваем количество трендов для экономии токенов
        limited_trends = trends[:5]  # Берём топ-5 трендов
        
        # Генерируем контент для каждого тренда и платформы
        tasks = []
        for trend in limited_trends:
            for platform in platforms:
                task = self.generate_content_for_trend(trend, platform)
                tasks.append((task, platform))
        
        # Выполняем задачи параллельно, но с ограничением
        semaphore = asyncio.Semaphore(3)  # Максимум 3 одновременных запроса
        
        async def limited_task(task_data):
            task, platform = task_data
            async with semaphore:
                return await task, platform
        
        results = await asyncio.gather(*[limited_task(task_data) for task_data in tasks])
        
        # Группируем результаты по платформам
        for content_item, platform in results:
            if content_item:
                content_batch[platform].append(content_item)
        
        self.logger.info(f"Создано {sum(len(items) for items in content_batch.values())} единиц контента")
        return content_batch

    def _extract_hashtags(self, content: str, platform: str) -> List[str]:
        """Извлечение или генерация хештегов из контента"""
        hashtags = []
        
        # Ищем существующие хештеги в контенте
        import re
        existing_tags = re.findall(r'#\w+', content)
        hashtags.extend([tag.lower() for tag in existing_tags])
        
        # Добавляем платформо-специфичные хештеги если их мало
        if len(hashtags) < 3:
            platform_hashtags = {
                "telegram": ["#новости", "#тренды", "#интересное"],
                "youtube_shorts": ["#shorts", "#тренд", "#вирусное"],  
                "tiktok": ["#fyp", "#viral", "#trending"],
                "instagram": ["#insta", "#reels", "#trending"]
            }
            hashtags.extend(platform_hashtags.get(platform, []))
        
        return list(set(hashtags[:10]))  # Убираем дубли и ограничиваем до 10

    def _create_fallback_content(self, trend: TrendItem, platform: str) -> ContentItem:
        """Создание запасного контента в случае ошибки LLM"""
        fallback_content = {
            "telegram": f"🔥 Актуальная тема: {trend.title}\n\n📈 Сейчас все обсуждают это! Что думаете?\n\n🔗 Подробнее: {trend.url}",
            "youtube_shorts": f"[ЗАСТАВКА] {trend.title}\n\n[ОСНОВНОЕ СОДЕРЖАНИЕ] Этот тренд покорил интернет! Расскажем всё самое важное за 60 секунд.\n\n[ПРИЗЫВ] Ставь лайк если интересно!",
            "tiktok": f"🔥 {trend.title} 🔥\n\nВсе говорят об этом! 😱\n\n#viral #тренд #fyp",
            "instagram": f"✨ {trend.title}\n\n🔥 Горячая тема дня! Что думаешь об этом?\n\n#trending #insta #hot"
        }
        
        return ContentItem(
            id=str(uuid.uuid4()),
            trend_id=trend.id,
            platform=platform,
            content_type="text",
            title=trend.title,
            content=fallback_content.get(platform, trend.title),
            hashtags=["#тренд", "#новости"],
            keywords=trend.keywords,
            timestamp=datetime.utcnow(),
            metadata={"fallback": True, "source_url": trend.url}
        )

    def generate_content_report(self, content_batch: Dict[str, List[ContentItem]]) -> Dict:
        """Генерация отчёта по созданному контенту"""
        report = {
            "total_content": sum(len(items) for items in content_batch.values()),
            "platforms": {},
            "top_hashtags": {},
            "generation_time": datetime.utcnow().isoformat(),
            "content_summary": []
        }
        
        for platform, content_items in content_batch.items():
            platform_stats = {
                "count": len(content_items),
                "avg_length": sum(len(item.content) for item in content_items) // len(content_items) if content_items else 0,
                "hashtags_count": sum(len(item.hashtags) for item in content_items)
            }
            report["platforms"][platform] = platform_stats
            
            # Подсчитываем популярные хештеги
            for item in content_items:
                for hashtag in item.hashtags:
                    report["top_hashtags"][hashtag] = report["top_hashtags"].get(hashtag, 0) + 1
            
            # Добавляем примеры контента
            for item in content_items[:2]:  # По 2 примера с каждой платформы
                report["content_summary"].append({
                    "platform": platform,
                    "title": item.title,
                    "content_preview": item.content[:100] + "..." if len(item.content) > 100 else item.content,
                    "hashtags": item.hashtags
                })
        
        return report


# Пример использования  
async def main():
    from trend_collector import TrendCollector
    
    # Собираем тренды
    collector = TrendCollector(youtube_api_key="AIzaSyCuWvZcQuOG8pPgkAMPY5_QmPaql7tZUcI")
    trends = await collector.collect_all_trends()
    
    # Генерируем контент
    generator = ContentGenerator(gemini_api_key="AIzaSyBSArxA7X_nUg-S41JketY3nLqR3VWGCTw")
    platforms = ["telegram", "youtube_shorts", "tiktok"]
    
    content_batch = await generator.generate_batch_content(trends[:3], platforms)
    
    # Показываем результаты
    for platform, content_items in content_batch.items():
        print(f"\n🎯 {platform.upper()} ({len(content_items)} постов):")
        for item in content_items:
            print(f"  📝 {item.title}")
            print(f"     {item.content[:100]}...")
            print(f"     🏷️ {', '.join(item.hashtags[:3])}")
    
    # Отчёт
    report = generator.generate_content_report(content_batch)
    print(f"\n📊 Создано {report['total_content']} единиц контента для {len(report['platforms'])} платформ")

if __name__ == "__main__":
    asyncio.run(main())