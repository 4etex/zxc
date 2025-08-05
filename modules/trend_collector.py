"""
EKOSYSTEMA_FULL - Сборщик трендов
Автоматический сбор трендовых тем из различных источников:
- YouTube RSS фиды
- Google Trends
- Reddit популярные посты
- Telegram каналы
"""
import asyncio
import aiohttp
import feedparser
import json
import uuid
import logging
from datetime import datetime
from typing import List, Dict, Optional
from pydantic import BaseModel
import os
from googleapiclient.discovery import build


class TrendItem(BaseModel):
    id: str
    title: str
    source: str
    url: str
    popularity_score: int
    keywords: List[str]
    timestamp: datetime
    description: str = ""
    category: str = ""

class TrendCollector:
    def __init__(self, youtube_api_key: str = None):
        self.logger = logging.getLogger(__name__)
        self.youtube_api_key = youtube_api_key
        
        # YouTube RSS фиды популярных каналов по категориям
        self.youtube_rss_feeds = {
            "tech": [
                "https://www.youtube.com/feeds/videos.xml?channel_id=UCBJycsmduvYEL83R_U4JriQ",  # MKBHD
                "https://www.youtube.com/feeds/videos.xml?channel_id=UCXuqSBlHAE6Xw-yeJA0Tunw",  # Linus Tech Tips
            ],
            "entertainment": [
                "https://www.youtube.com/feeds/videos.xml?channel_id=UCtxCXg-UvSnTKPOzLH4wJaQ",  # Ninja
                "https://www.youtube.com/feeds/videos.xml?channel_id=UCN7dywl5wDxTu1RM3eJ_h9Q",  # Ali-A
            ],
            "education": [
                "https://www.youtube.com/feeds/videos.xml?channel_id=UCsXVk37bltHxD1rDPwtNM8Q",  # Kurzgesagt
                "https://www.youtube.com/feeds/videos.xml?channel_id=UCsooa4yRKGN_zEE8iknghZA",  # TED-Ed
            ]
        }
        
        # Reddit популярные сабреддиты для трендов
        self.reddit_feeds = [
            "https://www.reddit.com/r/videos/hot/.rss",
            "https://www.reddit.com/r/Documentaries/hot/.rss",
            "https://www.reddit.com/r/todayilearned/hot/.rss",
            "https://www.reddit.com/r/technology/hot/.rss",
            "https://www.reddit.com/r/science/hot/.rss"
        ]

    async def collect_youtube_trends(self) -> List[TrendItem]:
        """Сбор трендов из YouTube RSS фидов"""
        trends = []
        
        async with aiohttp.ClientSession() as session:
            for category, feeds in self.youtube_rss_feeds.items():
                for feed_url in feeds:
                    try:
                        async with session.get(feed_url) as response:
                            if response.status == 200:
                                feed_content = await response.text()
                                feed = feedparser.parse(feed_content)
                                
                                for entry in feed.entries[:5]:  # Берём топ-5 видео
                                    trend = TrendItem(
                                        id=str(uuid.uuid4()),
                                        title=entry.title,
                                        source=f"YouTube-{category}",
                                        url=entry.link,
                                        popularity_score=self._calculate_youtube_score(entry),
                                        keywords=self._extract_keywords(entry.title),
                                        timestamp=datetime.utcnow(),
                                        description=entry.get('summary', ''),
                                        category=category
                                    )
                                    trends.append(trend)
                    except Exception as e:
                        self.logger.error(f"Ошибка при сборе YouTube трендов: {e}")
        
        return trends

    async def collect_reddit_trends(self) -> List[TrendItem]:
        """Сбор трендов из Reddit"""
        trends = []
        
        async with aiohttp.ClientSession() as session:
            for feed_url in self.reddit_feeds:
                try:
                    async with session.get(feed_url) as response:
                        if response.status == 200:
                            feed_content = await response.text()
                            feed = feedparser.parse(feed_content)
                            
                            for entry in feed.entries[:3]:  # Берём топ-3 поста
                                trend = TrendItem(
                                    id=str(uuid.uuid4()),
                                    title=entry.title,
                                    source="Reddit",
                                    url=entry.link,
                                    popularity_score=self._calculate_reddit_score(entry),
                                    keywords=self._extract_keywords(entry.title),
                                    timestamp=datetime.utcnow(),
                                    description=entry.get('summary', ''),
                                    category="social"
                                )
                                trends.append(trend)
                except Exception as e:
                    self.logger.error(f"Ошибка при сборе Reddit трендов: {e}")
        
        return trends

    def collect_youtube_api_trends(self) -> List[TrendItem]:
        """Сбор трендов через YouTube Data API"""
        if not self.youtube_api_key:
            return []
            
        trends = []
        try:
            youtube = build('youtube', 'v3', developerKey=self.youtube_api_key)
            
            # Получаем популярные видео
            request = youtube.videos().list(
                part='snippet,statistics',
                chart='mostPopular',
                regionCode='RU',
                maxResults=20
            )
            response = request.execute()
            
            for video in response.get('items', []):
                snippet = video['snippet']
                stats = video['statistics']
                
                trend = TrendItem(
                    id=str(uuid.uuid4()),
                    title=snippet['title'],
                    source="YouTube-API",
                    url=f"https://www.youtube.com/watch?v={video['id']}",
                    popularity_score=int(stats.get('viewCount', 0)) // 1000,  # Упрощённый счёт
                    keywords=self._extract_keywords(snippet['title']),
                    timestamp=datetime.utcnow(),
                    description=snippet.get('description', '')[:200],
                    category=snippet.get('categoryId', 'unknown')
                )
                trends.append(trend)
                
        except Exception as e:
            self.logger.error(f"Ошибка YouTube API: {e}")
        
        return trends

    def _calculate_youtube_score(self, entry) -> int:
        """Простой алгоритм подсчёта популярности для YouTube"""
        score = 50  # Базовая популярность
        
        # Учитываем время публикации (свежие видео получают больше очков)
        if hasattr(entry, 'published_parsed'):
            pub_time = datetime(*entry.published_parsed[:6])
            hours_old = (datetime.utcnow() - pub_time).total_seconds() / 3600
            if hours_old < 24:
                score += 30
            elif hours_old < 48:
                score += 15
        
        return score

    def _calculate_reddit_score(self, entry) -> int:
        """Простой алгоритм подсчёта популярности для Reddit"""
        # Reddit RSS не содержит счётчиков, используем базовую логику
        score = 40
        
        # Проверяем на "горячие" слова в заголовке
        hot_words = ['viral', 'trending', 'amazing', 'incredible', 'shocking']
        for word in hot_words:
            if word.lower() in entry.title.lower():
                score += 10
                
        return score

    def _extract_keywords(self, text: str) -> List[str]:
        """Извлечение ключевых слов из текста"""
        # Простое извлечение - убираем стоп-слова и берём значимые слова
        stop_words = {'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by',
                     'и', 'в', 'на', 'с', 'по', 'для', 'от', 'до', 'как', 'что', 'или', 'но'}
        
        words = text.lower().replace(',', ' ').replace('.', ' ').replace('!', ' ').replace('?', ' ').split()
        keywords = [word for word in words if len(word) > 3 and word not in stop_words]
        
        return keywords[:5]  # Возвращаем топ-5 ключевых слов

    async def collect_all_trends(self) -> List[TrendItem]:
        """Сбор всех трендов из всех источников"""
        all_trends = []
        
        # Параллельно собираем тренды из разных источников
        youtube_trends = await self.collect_youtube_trends()
        reddit_trends = await self.collect_reddit_trends()
        api_trends = self.collect_youtube_api_trends()
        
        all_trends.extend(youtube_trends)
        all_trends.extend(reddit_trends)  
        all_trends.extend(api_trends)
        
        # Сортируем по популярности
        all_trends.sort(key=lambda x: x.popularity_score, reverse=True)
        
        self.logger.info(f"Собрано {len(all_trends)} трендов")
        return all_trends[:30]  # Возвращаем топ-30 трендов

    def get_trend_report(self, trends: List[TrendItem]) -> Dict:
        """Генерация отчёта по трендам"""
        if not trends:
            return {"error": "Нет доступных трендов"}
            
        report = {
            "total_trends": len(trends),
            "top_sources": {},
            "top_categories": {},
            "top_keywords": {},
            "timestamp": datetime.utcnow().isoformat(),
            "trends_summary": []
        }
        
        # Анализируем источники
        for trend in trends:
            source = trend.source
            report["top_sources"][source] = report["top_sources"].get(source, 0) + 1
            
            category = trend.category
            report["top_categories"][category] = report["top_categories"].get(category, 0) + 1
            
            # Подсчитываем ключевые слова
            for keyword in trend.keywords:
                report["top_keywords"][keyword] = report["top_keywords"].get(keyword, 0) + 1
            
            # Добавляем краткую информацию о тренде
            report["trends_summary"].append({
                "title": trend.title,
                "source": trend.source,
                "score": trend.popularity_score,
                "url": trend.url
            })
        
        return report


# Пример использования
async def main():
    collector = TrendCollector(youtube_api_key="AIzaSyCuWvZcQuOG8pPgkAMPY5_QmPaql7tZUcI")
    trends = await collector.collect_all_trends()
    
    print(f"🔥 Найдено {len(trends)} актуальных трендов:")
    for i, trend in enumerate(trends[:5], 1):
        print(f"{i}. {trend.title} (Score: {trend.popularity_score})")
    
    # Генерируем отчёт
    report = collector.get_trend_report(trends)
    print(f"\n📊 Отчёт: {report['total_trends']} трендов из {len(report['top_sources'])} источников")

if __name__ == "__main__":
    asyncio.run(main())