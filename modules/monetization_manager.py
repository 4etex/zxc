"""
Модуль партнерских ссылок и монетизации для EKOSYSTEMA_FULL
Управляет CPA ссылками, реферальными программами и монетизацией контента
"""

import os
import logging
import uuid
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import asyncio
import aiohttp
from pathlib import Path
import json
import hashlib

logger = logging.getLogger(__name__)

class AffiliateLink:
    """Модель партнерской ссылки"""
    def __init__(self, link_id: str, platform: str, url: str, commission_rate: float,
                 category: str, description: str = "", is_active: bool = True):
        self.id = link_id
        self.platform = platform
        self.url = url
        self.commission_rate = commission_rate
        self.category = category
        self.description = description
        self.is_active = is_active
        self.clicks = 0
        self.conversions = 0
        self.earnings = 0.0
        self.created_at = datetime.now()
        
    def to_dict(self):
        return {
            "id": self.id,
            "platform": self.platform,
            "url": self.url,
            "commission_rate": self.commission_rate,
            "category": self.category,
            "description": self.description,
            "is_active": self.is_active,
            "clicks": self.clicks,
            "conversions": self.conversions,
            "earnings": self.earnings,
            "created_at": self.created_at.isoformat()
        }

class MonetizationManager:
    """Менеджер монетизации и партнерских программ"""
    
    def __init__(self):
        self.links = []
        self.telegram_refs = []
        self.earnings_data = {}
        
        # Настройки CPA сетей
        self.cpa_networks = {
            "admitad": {
                "name": "Admitad",
                "api_url": "https://api.admitad.com/",
                "categories": ["telegram", "finance", "crypto", "education"]
            },
            "cityads": {
                "name": "CityAds", 
                "api_url": "https://api.cityads.com/",
                "categories": ["shopping", "services", "apps"]
            },
            "telegram_programs": {
                "name": "Telegram Programs",
                "categories": ["bots", "channels", "mini_apps", "stars"]
            }
        }
        
        # Предустановленные тематические ссылки
        self._initialize_default_links()
    
    def _initialize_default_links(self):
        """Инициализирует базовые партнерские ссылки"""
        default_links = [
            {
                "platform": "telegram",
                "url": "https://t.me/BotFather?start=ref123",
                "commission_rate": 5.0,
                "category": "telegram_bots",
                "description": "Создание Telegram ботов - заработок до $500/мес"
            },
            {
                "platform": "crypto",
                "url": "https://example-crypto-exchange.com/ref/123456",
                "commission_rate": 30.0,
                "category": "crypto_exchange",
                "description": "Криптобиржа - комиссия с каждой сделки"
            },
            {
                "platform": "education", 
                "url": "https://example-course.com/?ref=content123",
                "commission_rate": 40.0,
                "category": "online_courses",
                "description": "Онлайн курсы по заработку в интернете"
            },
            {
                "platform": "telegram",
                "url": "https://t.me/premium",
                "commission_rate": 15.0,
                "category": "telegram_premium",
                "description": "Telegram Premium подписка"
            }
        ]
        
        for link_data in default_links:
            link = AffiliateLink(
                link_id=str(uuid.uuid4()),
                **link_data
            )
            self.links.append(link)
        
        logger.info(f"Инициализировано {len(self.links)} партнерских ссылок")
    
    async def find_relevant_links(self, content: str, category: str = None, 
                                platform: str = None) -> List[AffiliateLink]:
        """Находит релевантные партнерские ссылки для контента"""
        relevant_links = []
        
        # Ключевые слова для поиска релевантных ссылок
        keywords_map = {
            "telegram": ["телеграм", "telegram", "бот", "канал", "чат"],
            "crypto": ["крипто", "bitcoin", "биткоин", "блокчейн", "криптовалюта"],
            "finance": ["заработок", "деньги", "доход", "финансы", "инвестиции"],
            "education": ["курс", "обучение", "навыки", "знания", "учиться"]
        }
        
        content_lower = content.lower()
        
        for link in self.links:
            if not link.is_active:
                continue
                
            # Фильтр по платформе
            if platform and link.platform != platform:
                continue
                
            # Фильтр по категории
            if category and link.category != category:
                continue
            
            # Поиск по ключевым словам
            link_keywords = keywords_map.get(link.platform, [])
            if any(keyword in content_lower for keyword in link_keywords):
                relevant_links.append(link)
        
        # Сортируем по комиссии (выше комиссия = выше приоритет)
        relevant_links.sort(key=lambda x: x.commission_rate, reverse=True)
        
        return relevant_links[:3]  # Максимум 3 ссылки на контент
    
    def generate_tracked_link(self, affiliate_link: AffiliateLink, 
                            content_id: str = None) -> str:
        """Генерирует отслеживаемую ссылку"""
        # Создаем уникальный трекинг код
        tracking_data = f"{affiliate_link.id}_{content_id}_{datetime.now().timestamp()}"
        tracking_hash = hashlib.md5(tracking_data.encode()).hexdigest()[:8]
        
        # Добавляем трекинг параметры к ссылке
        separator = "&" if "?" in affiliate_link.url else "?"
        tracked_url = f"{affiliate_link.url}{separator}utm_source=ekosystema&utm_campaign={tracking_hash}"
        
        return tracked_url
    
    async def inject_affiliate_links(self, content: Dict, max_links: int = 2) -> Dict:
        """Внедряет партнерские ссылки в контент"""
        try:
            content_text = content.get("content", "")
            platform = content.get("platform", "")
            
            # Находим релевантные ссылки
            relevant_links = await self.find_relevant_links(content_text, platform=platform)
            
            if not relevant_links:
                return content
            
            selected_links = relevant_links[:max_links]
            
            # Добавляем ссылки в конец контента
            content_with_links = content.copy()
            original_content = content_with_links.get("content", "")
            
            link_section = "\n\n🔗 Полезные ссылки:\n"
            for i, link in enumerate(selected_links, 1):
                tracked_url = self.generate_tracked_link(link, content.get("id"))
                link_section += f"{i}. {link.description}\n{tracked_url}\n\n"
            
            content_with_links["content"] = original_content + link_section
            
            # Добавляем метаданные о ссылках
            content_with_links["affiliate_links"] = [
                {
                    "id": link.id,
                    "platform": link.platform,
                    "commission_rate": link.commission_rate,
                    "tracked_url": self.generate_tracked_link(link, content.get("id"))
                }
                for link in selected_links
            ]
            
            logger.info(f"Добавлено {len(selected_links)} партнерских ссылок в контент")
            return content_with_links
            
        except Exception as e:
            logger.error(f"Ошибка внедрения партнерских ссылок: {e}")
            return content
    
    async def generate_telegram_referral(self, bot_username: str, 
                                       campaign: str = "default") -> str:
        """Генерирует реферальную ссылку для Telegram бота"""
        ref_code = f"ref_{campaign}_{uuid.uuid4().hex[:8]}"
        ref_link = f"https://t.me/{bot_username}?start={ref_code}"
        
        # Сохраняем реферальную ссылку
        self.telegram_refs.append({
            "code": ref_code,
            "bot": bot_username,
            "campaign": campaign,
            "created_at": datetime.now(),
            "clicks": 0,
            "conversions": 0
        })
        
        return ref_link
    
    async def track_click(self, link_id: str, user_id: str = None):
        """Отслеживает клик по партнерской ссылке"""
        for link in self.links:
            if link.id == link_id:
                link.clicks += 1
                logger.info(f"Клик по ссылке {link_id}: {link.clicks} всего кликов")
                break
    
    async def track_conversion(self, link_id: str, amount: float = 0.0):
        """Отслеживает конверсию по партнерской ссылке"""
        for link in self.links:
            if link.id == link_id:
                link.conversions += 1
                link.earnings += amount * (link.commission_rate / 100)
                logger.info(f"Конверсия по ссылке {link_id}: +${amount:.2f}")
                break
    
    def get_earnings_report(self, days: int = 30) -> Dict:
        """Генерирует отчет о доходах"""
        total_clicks = sum(link.clicks for link in self.links)
        total_conversions = sum(link.conversions for link in self.links)
        total_earnings = sum(link.earnings for link in self.links)
        
        # Группируем по платформам
        platform_stats = {}
        for link in self.links:
            if link.platform not in platform_stats:
                platform_stats[link.platform] = {
                    "clicks": 0,
                    "conversions": 0,
                    "earnings": 0.0,
                    "links_count": 0
                }
            
            platform_stats[link.platform]["clicks"] += link.clicks
            platform_stats[link.platform]["conversions"] += link.conversions
            platform_stats[link.platform]["earnings"] += link.earnings
            platform_stats[link.platform]["links_count"] += 1
        
        return {
            "period_days": days,
            "total_stats": {
                "clicks": total_clicks,
                "conversions": total_conversions,
                "earnings": round(total_earnings, 2),
                "conversion_rate": round((total_conversions / max(total_clicks, 1)) * 100, 2)
            },
            "platform_stats": platform_stats,
            "top_links": sorted(
                [link.to_dict() for link in self.links if link.earnings > 0],
                key=lambda x: x["earnings"],
                reverse=True
            )[:5]
        }
    
    async def optimize_content_monetization(self, content_batch: Dict) -> Dict:
        """Оптимизирует монетизацию для батча контента"""
        optimized_batch = {}
        
        for platform, content_items in content_batch.items():
            optimized_items = []
            
            for content in content_items:
                # Добавляем партнерские ссылки
                monetized_content = await self.inject_affiliate_links(
                    content.dict() if hasattr(content, 'dict') else content
                )
                
                # Добавляем призывы к действию
                monetized_content = self._add_call_to_action(monetized_content, platform)
                
                optimized_items.append(monetized_content)
            
            optimized_batch[platform] = optimized_items
        
        return optimized_batch
    
    def _add_call_to_action(self, content: Dict, platform: str) -> Dict:
        """Добавляет призывы к действию в контент"""
        cta_templates = {
            "telegram": [
                "👆 Переходи по ссылке и начинай зарабатывать уже сегодня!",
                "💰 Не упусти шанс получить пассивный доход!",
                "🚀 Кликай и получи бонус к первой покупке!"
            ],
            "youtube_shorts": [
                "👆 Ссылка в описании - переходи и зарабатывай!",
                "💎 Лайк если помогло + ссылка в описании!",
                "🔥 Подписывайся и переходи по ссылке в описании!"
            ],
            "tiktok": [
                "👆 Линк в профиле - переходи быстрее!",
                "💰 Проверенный способ в профиле!",
                "🚀 Еще больше способов в профиле!"
            ]
        }
        
        ctas = cta_templates.get(platform, cta_templates["telegram"])
        
        # Выбираем случайный CTA
        import random
        selected_cta = random.choice(ctas)
        
        # Добавляем в конец контента
        enhanced_content = content.copy()
        original_text = enhanced_content.get("content", "")
        enhanced_content["content"] = f"{original_text}\n\n{selected_cta}"
        
        return enhanced_content
    
    def add_custom_affiliate_link(self, platform: str, url: str, commission_rate: float,
                                category: str, description: str = "") -> str:
        """Добавляет пользовательскую партнерскую ссылку"""
        link = AffiliateLink(
            link_id=str(uuid.uuid4()),
            platform=platform,
            url=url,
            commission_rate=commission_rate,
            category=category,
            description=description
        )
        
        self.links.append(link)
        logger.info(f"Добавлена партнерская ссылка: {platform} - {commission_rate}%")
        return link.id

# Пример использования
async def main():
    monetization = MonetizationManager()
    
    # Тестовый контент
    test_content = {
        "id": "test_content_1",
        "title": "Как заработать в Telegram",
        "content": "Сегодня расскажу про топ способы заработка в телеграм. Это реально работает!",
        "platform": "telegram"
    }
    
    # Добавляем партнерские ссылки
    monetized = await monetization.inject_affiliate_links(test_content)
    print("Монетизированный контент:")
    print(monetized["content"])
    
    # Отчет о доходах
    report = monetization.get_earnings_report()
    print("\nОтчет о доходах:")
    print(f"Общий доход: ${report['total_stats']['earnings']}")

if __name__ == "__main__":
    asyncio.run(main())