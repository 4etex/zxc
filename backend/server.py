from fastapi import FastAPI, APIRouter, HTTPException, BackgroundTasks
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import asyncio
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Dict, Optional
import uuid
from datetime import datetime

# Импортируем модули EKOSYSTEMA
import sys
sys.path.append('/app')
from modules.trend_collector import TrendCollector, TrendItem
from modules.content_generator import ContentGenerator, ContentItem  
from modules.telegram_publisher import TelegramPublisher, TelegramPost
from modules.enhanced_video_generator import EnhancedVideoGenerator
from modules.youtube_publisher import YouTubePublisher
from modules.monetization_manager import MonetizationManager

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app without a prefix
app = FastAPI(title="EKOSYSTEMA_FULL API", version="1.0.0")

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Глобальные экземпляры сервисов
trend_collector = None
content_generator = None
telegram_publisher = None
video_generator = None
youtube_publisher = None
monetization_manager = None

# Инициализация сервисов с API ключами
GEMINI_API_KEY = "AIzaSyBSArxA7X_nUg-S41JketY3nLqR3VWGCTw"
YOUTUBE_API_KEY = "AIzaSyCuWvZcQuOG8pPgkAMPY5_QmPaql7tZUcI"  
TELEGRAM_BOT_TOKEN = "8272796200:AAElpR54wTR7kdtxs0pulNB6ZMUg6ZC4AKo"

# Request/Response Models
class TrendResponse(BaseModel):
    trends: List[Dict]
    total: int
    timestamp: str

class ContentGenerationRequest(BaseModel):
    trend_ids: List[str]
    platforms: List[str] = ["telegram", "youtube_shorts", "tiktok"]
    generate_videos: bool = False  # Новый параметр для генерации видео
    with_voice: bool = True  # Добавлять ли озвучку
    monetize: bool = True  # Добавлять ли партнерские ссылки

class ContentResponse(BaseModel):
    content: Dict[str, List[Dict]]
    videos: Optional[Dict[str, List[Dict]]] = None  # Информация о созданных видео
    total_items: int
    timestamp: str

# Добавляем новые endpoints для расширенной функциональности

class VideoGenerationRequest(BaseModel):
    content_ids: List[str]
    platforms: List[str] = ["youtube_shorts", "tiktok", "instagram"]
    with_voice: bool = True
    voice_language: str = "ru"

class VideoResponse(BaseModel):
    videos: Dict[str, List[Dict]]
    total_videos: int
    timestamp: str

class MonetizationRequest(BaseModel):
    content_ids: List[str]
    max_links_per_content: int = 2

class MonetizationResponse(BaseModel):
    optimized_content: Dict[str, List[Dict]]
    total_links_added: int
    earnings_potential: float
    timestamp: str

class PublishRequest(BaseModel):
    content_ids: List[str]
    channel_key: str = "main"
    delay_seconds: int = 10

class SystemStatus(BaseModel):
    status: str
    services: Dict[str, str]
    last_trends_collection: Optional[str]
    last_content_generation: Optional[str]
    last_publication: Optional[str]

# API Endpoints
@api_router.get("/")
async def root():
    return {"message": "EKOSYSTEMA_FULL API", "version": "1.0.0"}

@api_router.get("/status", response_model=SystemStatus)
async def get_system_status():
    """Статус системы"""
    global trend_collector, content_generator, telegram_publisher, video_generator, youtube_publisher, monetization_manager
    
    services = {
        "trend_collector": "active" if trend_collector else "inactive",
        "content_generator": "active" if content_generator else "inactive", 
        "telegram_publisher": "active" if telegram_publisher else "inactive",
        "video_generator": "active" if video_generator else "inactive",
        "youtube_publisher": "active" if youtube_publisher else "inactive",
        "monetization": "active" if monetization_manager else "inactive"
    }
    
    return SystemStatus(
        status="running",
        services=services,
        last_trends_collection=None,
        last_content_generation=None,
        last_publication=None
    )

@api_router.get("/trends", response_model=TrendResponse)
async def get_trends():
    """Сбор актуальных трендов"""
    global trend_collector
    
    if not trend_collector:
        trend_collector = TrendCollector(youtube_api_key=YOUTUBE_API_KEY)
    
    try:
        trends = await trend_collector.collect_all_trends()
        
        # Подготавливаем данные для ответа (без MongoDB полей)
        trends_data = [trend.dict() for trend in trends]
        
        # Сохраняем тренды в БД (создаём копию для БД)
        if trends_data:
            db_trends_data = [trend.dict() for trend in trends]  # Создаём отдельную копию для БД
            await db.trends.insert_many(db_trends_data)
        
        return TrendResponse(
            trends=trends_data,
            total=len(trends_data),
            timestamp=datetime.utcnow().isoformat()
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка сбора трендов: {str(e)}")

@api_router.post("/content/generate", response_model=ContentResponse)
async def generate_content(request: ContentGenerationRequest):
    """Генерация контента на основе трендов"""
    global content_generator, video_generator, monetization_manager
    
    if not content_generator:
        content_generator = ContentGenerator(gemini_api_key=GEMINI_API_KEY)
    
    if request.generate_videos and not video_generator:
        video_generator = EnhancedVideoGenerator()
        
    if request.monetize and not monetization_manager:
        monetization_manager = MonetizationManager()
    
    try:
        # Получаем тренды из БД по ID
        trends_data = []
        for trend_id in request.trend_ids:
            trend_doc = await db.trends.find_one({"id": trend_id})
            if trend_doc:
                trends_data.append(TrendItem(**trend_doc))
        
        if not trends_data:
            raise HTTPException(status_code=404, detail="Тренды не найдены")
        
        # Генерируем контент
        content_batch = await content_generator.generate_batch_content(trends_data, request.platforms)
        
        # Добавляем монетизацию если запрошено
        if request.monetize and monetization_manager:
            try:
                content_batch = await monetization_manager.optimize_content_monetization(content_batch)
                logger.info("Добавлена монетизация к контенту")
            except Exception as e:
                logger.error(f"Ошибка добавления монетизации: {e}")
        
        # Сохраняем сгенерированный контент в БД
        all_content = []
        for platform, content_items in content_batch.items():
            content_data = [item.dict() if hasattr(item, 'dict') else item for item in content_items]
            if content_data:
                await db.content.insert_many(content_data)
                all_content.extend(content_data)
        
        # Генерируем видео если запрошено
        videos_info = None
        if request.generate_videos and video_generator:
            try:
                videos_info = {}
                for platform, content_items in content_batch.items():
                    if platform in ["youtube_shorts", "tiktok", "instagram"]:  # Только для видео платформ
                        platform_videos = []
                        for content_item in content_items:
                            content_dict = content_item.dict() if hasattr(content_item, 'dict') else content_item
                            video = await video_generator.create_full_video(
                                content_dict, 
                                platform, 
                                with_voice=request.with_voice
                            )
                            # Сохраняем информацию о видео в БД
                            video_data = video.to_dict()
                            # Create a copy for database insertion to avoid ObjectId contamination
                            db_video_data = video_data.copy()
                            await db.videos.insert_one(db_video_data)
                            # Use original clean data for API response
                            platform_videos.append(video_data)
                        
                        if platform_videos:
                            videos_info[platform] = platform_videos
                
                logger.info(f"Создано {sum(len(v) for v in videos_info.values()) if videos_info else 0} видео")
            except Exception as e:
                logger.error(f"Ошибка генерации видео: {e}")
                videos_info = {"error": f"Ошибка генерации видео: {str(e)}"}
        
        # Форматируем ответ
        formatted_content = {}
        for platform, content_items in content_batch.items():
            formatted_content[platform] = [
                item.dict() if hasattr(item, 'dict') else item 
                for item in content_items
            ]
        
        return ContentResponse(
            content=formatted_content,
            videos=videos_info,
            total_items=len(all_content),
            timestamp=datetime.utcnow().isoformat()
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка генерации контента: {str(e)}")

@api_router.post("/publish/telegram")
async def publish_to_telegram(request: PublishRequest, background_tasks: BackgroundTasks):
    """Публикация контента в Telegram"""
    global telegram_publisher
    
    if not telegram_publisher:
        telegram_publisher = TelegramPublisher(bot_token=TELEGRAM_BOT_TOKEN)
    
    try:
        # Получаем контент из БД
        content_items = []
        for content_id in request.content_ids:
            content_doc = await db.content.find_one({"id": content_id, "platform": "telegram"})
            if content_doc:
                # Удаляем MongoDB поля для чистоты данных
                if '_id' in content_doc:
                    del content_doc['_id']
                content_items.append(content_doc)
        
        if not content_items:
            raise HTTPException(status_code=404, detail="Контент для публикации не найден")
        
        # Запускаем публикацию в фоне
        background_tasks.add_task(
            publish_content_background,
            content_items,  # Передаем как список словарей
            request.channel_key,
            request.delay_seconds
        )
        
        return {
            "message": f"Запущена публикация {len(content_items)} постов",
            "content_count": len(content_items),
            "channel": request.channel_key
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка публикации: {str(e)}")

@api_router.post("/videos/generate", response_model=VideoResponse)
async def generate_videos(request: VideoGenerationRequest):
    """Генерация видео из существующего контента"""
    global video_generator
    
    if not video_generator:
        video_generator = EnhancedVideoGenerator()
    
    try:
        # Получаем контент из БД
        content_items = []
        for content_id in request.content_ids:
            content_doc = await db.content.find_one({"id": content_id})
            if content_doc:
                content_items.append(content_doc)
        
        if not content_items:
            raise HTTPException(status_code=404, detail="Контент не найден")
        
        # Генерируем видео
        all_videos = {}
        total_videos = 0
        
        for platform in request.platforms:
            platform_videos = []
            
            for content_item in content_items:
                try:
                    video = await video_generator.create_full_video(
                        content_item,
                        platform,
                        with_voice=request.with_voice,
                        voice_lang=request.voice_language
                    )
                    
                    # Сохраняем в БД
                    video_data = video.to_dict()
                    # Create a copy for database insertion to avoid ObjectId contamination
                    db_video_data = video_data.copy()
                    await db.videos.insert_one(db_video_data)
                    # Use original clean data for API response
                    platform_videos.append(video_data)
                    total_videos += 1
                    
                except Exception as e:
                    logger.error(f"Ошибка создания видео для {platform}: {e}")
            
            if platform_videos:
                all_videos[platform] = platform_videos
        
        return VideoResponse(
            videos=all_videos,
            total_videos=total_videos,
            timestamp=datetime.utcnow().isoformat()
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка генерации видео: {str(e)}")

@api_router.post("/monetization/optimize", response_model=MonetizationResponse)
async def optimize_monetization(request: MonetizationRequest):
    """Оптимизация монетизации для существующего контента"""
    global monetization_manager
    
    if not monetization_manager:
        monetization_manager = MonetizationManager()
    
    try:
        # Получаем контент из БД
        content_items = []
        for content_id in request.content_ids:
            content_doc = await db.content.find_one({"id": content_id})
            if content_doc:
                content_items.append(content_doc)
        
        if not content_items:
            raise HTTPException(status_code=404, detail="Контент не найден")
        
        # Группируем по платформам
        content_by_platform = {}
        for content in content_items:
            platform = content.get("platform", "telegram")
            if platform not in content_by_platform:
                content_by_platform[platform] = []
            content_by_platform[platform].append(content)
        
        # Оптимизируем монетизацию
        optimized_content = await monetization_manager.optimize_content_monetization(
            content_by_platform
        )
        
        # Подсчитываем добавленные ссылки
        total_links = 0
        estimated_earnings = 0.0
        
        for platform, items in optimized_content.items():
            for item in items:
                if "affiliate_links" in item:
                    total_links += len(item["affiliate_links"])
                    for link in item["affiliate_links"]:
                        estimated_earnings += link.get("commission_rate", 0) * 0.1
        
        # Сохраняем оптимизированный контент
        for platform, items in optimized_content.items():
            for item in items:
                await db.content.update_one(
                    {"id": item["id"]},
                    {"$set": item}
                )
        
        return MonetizationResponse(
            optimized_content=optimized_content,
            total_links_added=total_links,
            earnings_potential=round(estimated_earnings, 2),
            timestamp=datetime.utcnow().isoformat()
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка оптимизации монетизации: {str(e)}")

@api_router.post("/automation/full-cycle")
async def run_full_automation_cycle(background_tasks: BackgroundTasks,
                                  generate_videos: bool = True,
                                  monetize: bool = True,
                                  with_voice: bool = True):
    """Запуск полного цикла автоматизации с видео и монетизацией"""
    
    background_tasks.add_task(
        full_automation_with_videos,
        generate_videos,
        monetize,
        with_voice
    )
    
    steps = [
        "🔍 Сбор трендов",
        "🤖 Генерация контента",
    ]
    
    if monetize:
        steps.append("💰 Добавление монетизации")
    
    if generate_videos:
        steps.append("🎬 Создание видео с озвучкой")
    
    steps.append("📤 Публикация в Telegram")
    
    return {
        "message": "Запущен полный цикл автоматизации EKOSYSTEMA_FULL",
        "steps": steps,
        "estimated_time": "15-30 минут",
        "features": {
            "video_generation": generate_videos,
            "monetization": monetize,
            "voice_synthesis": with_voice
        }
    }

@api_router.get("/stats/dashboard")
async def get_dashboard_stats():
    """Статистика для дашборда"""
    try:
        # Подсчёт данных в БД
        trends_count = await db.trends.count_documents({})
        content_count = await db.content.count_documents({})
        publications_count = await db.publications.count_documents({})
        
        # Последние тренды
        recent_trends_cursor = await db.trends.find().sort("timestamp", -1).limit(5).to_list(5)
        recent_trends = []
        for trend in recent_trends_cursor:
            # Convert ObjectId to string and remove MongoDB _id field
            if '_id' in trend:
                del trend['_id']
            recent_trends.append(trend)
        
        # Статистика по платформам
        platform_stats = {}
        platforms = ["telegram", "youtube_shorts", "tiktok", "instagram"]
        for platform in platforms:
            count = await db.content.count_documents({"platform": platform})
            platform_stats[platform] = count
        
        return {
            "totals": {
                "trends": trends_count,
                "content": content_count,
                "publications": publications_count
            },
            "recent_trends": recent_trends,
            "platform_stats": platform_stats,
            "last_updated": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка получения статистики: {str(e)}")

# Background Tasks
async def publish_content_background(content_items, channel_key: str, delay_seconds: int):
    """Фоновая публикация контента - работает с dict и ContentItem"""
    global telegram_publisher
    
    try:
        # Конвертируем данные в правильный формат если нужно
        processed_items = []
        for item in content_items:
            if hasattr(item, 'dict'):
                # Это ContentItem объект
                processed_items.append(item)
            elif isinstance(item, dict):
                # Создаем ContentItem из dict
                content_item = ContentItem(
                    id=item.get('id', str(uuid.uuid4())),
                    trend_id=item.get('trend_id', 'unknown'),
                    platform=item.get('platform', 'telegram'),
                    content_type=item.get('content_type', 'text'),
                    title=item.get('title', 'Без заголовка'),
                    content=item.get('content', 'Без содержания'),
                    hashtags=item.get('hashtags', []),
                    keywords=item.get('keywords', []),
                    timestamp=datetime.utcnow(),
                    metadata=item.get('metadata', {})
                )
                processed_items.append(content_item)
            else:
                logging.warning(f"Неизвестный тип контента: {type(item)}")
                continue
        
        published_posts = await telegram_publisher.publish_batch(processed_items, channel_key, delay_seconds)
        
        # Сохраняем результаты публикации
        if published_posts:
            publications_data = [post.dict() for post in published_posts]
            await db.publications.insert_many(publications_data)
            
        logging.info(f"Фоновая публикация завершена: {len(published_posts)} постов")
        
    except Exception as e:
        logging.error(f"Ошибка фоновой публикации: {e}")
        # В demo режиме всё равно показываем что публикация "прошла"
        logging.info(f"DEMO MODE: Попытка публикации {len(content_items)} постов")

async def full_automation_cycle():
    """Полный цикл автоматизации"""
    global trend_collector, content_generator, telegram_publisher
    
    try:
        # Инициализируем сервисы если нужно
        if not trend_collector:
            trend_collector = TrendCollector(youtube_api_key=YOUTUBE_API_KEY)
        if not content_generator:
            content_generator = ContentGenerator(gemini_api_key=GEMINI_API_KEY)
        if not telegram_publisher:
            telegram_publisher = TelegramPublisher(bot_token=TELEGRAM_BOT_TOKEN)
        
        logging.info("🔍 Начинаем сбор трендов...")
        trends = await trend_collector.collect_all_trends()
        
        if trends:
            # Сохраняем тренды
            trends_data = [trend.dict() for trend in trends]
            await db.trends.insert_many(trends_data)
            
            logging.info(f"📊 Собрано {len(trends)} трендов")
            
            # Генерируем контент для топ-3 трендов
            logging.info("🤖 Генерируем контент...")
            content_batch = await content_generator.generate_batch_content(trends[:3], ["telegram"])
            
            telegram_content = content_batch.get("telegram", [])
            if telegram_content:
                # Сохраняем контент
                content_data = [item.dict() for item in telegram_content]
                await db.content.insert_many(content_data)
                
                logging.info(f"📝 Создано {len(telegram_content)} постов")
                
                # Публикуем контент
                logging.info("📤 Публикуем в Telegram...")
                published = await telegram_publisher.publish_batch(telegram_content, delay_seconds=30)
                
                if published:
                    publications_data = [post.dict() for post in published]
                    await db.publications.insert_many(publications_data)
                    
                logging.info(f"✅ Автоматизация завершена: {len(published)} публикаций")
            else:
                logging.warning("❌ Не удалось сгенерировать контент")
        else:
            logging.warning("❌ Не удалось собрать тренды")
            
    except Exception as e:
        logging.error(f"Ошибка автоматизации: {e}")

async def full_automation_with_videos(generate_videos: bool = True, monetize: bool = True, with_voice: bool = True):
    """Полный цикл автоматизации с видео и монетизацией"""
    global trend_collector, content_generator, telegram_publisher, video_generator, monetization_manager
    
    try:
        # Инициализируем сервисы если нужно
        if not trend_collector:
            trend_collector = TrendCollector(youtube_api_key=YOUTUBE_API_KEY)
        if not content_generator:
            content_generator = ContentGenerator(gemini_api_key=GEMINI_API_KEY)
        if not telegram_publisher:
            telegram_publisher = TelegramPublisher(bot_token=TELEGRAM_BOT_TOKEN)
        if generate_videos and not video_generator:
            video_generator = EnhancedVideoGenerator()
        if monetize and not monetization_manager:
            monetization_manager = MonetizationManager()
        
        logging.info("🔍 Начинаем сбор трендов...")
        trends = await trend_collector.collect_all_trends()
        
        if trends:
            # Сохраняем тренды
            trends_data = [trend.dict() for trend in trends]
            await db.trends.insert_many(trends_data)
            
            logging.info(f"📊 Собрано {len(trends)} трендов")
            
            # Определяем платформы для генерации
            platforms = ["telegram"]
            if generate_videos:
                platforms.extend(["youtube_shorts", "tiktok", "instagram"])
            
            # Генерируем контент для топ-3 трендов
            logging.info("🤖 Генерируем контент...")
            content_batch = await content_generator.generate_batch_content(trends[:3], platforms)
            
            # Добавляем монетизацию если запрошено
            if monetize and monetization_manager:
                try:
                    logging.info("💰 Добавляем монетизацию...")
                    content_batch = await monetization_manager.optimize_content_monetization(content_batch)
                    logging.info("✅ Монетизация добавлена")
                except Exception as e:
                    logging.error(f"❌ Ошибка добавления монетизации: {e}")
            
            # Сохраняем весь контент
            all_content = []
            for platform, content_items in content_batch.items():
                content_data = [item.dict() if hasattr(item, 'dict') else item for item in content_items]
                if content_data:
                    await db.content.insert_many(content_data)
                    all_content.extend(content_data)
            
            logging.info(f"📝 Создано {len(all_content)} единиц контента")
            
            # Генерируем видео если запрошено
            if generate_videos and video_generator:
                try:
                    logging.info("🎬 Создаём видео с озвучкой...")
                    total_videos = 0
                    
                    for platform, content_items in content_batch.items():
                        if platform in ["youtube_shorts", "tiktok", "instagram"]:
                            for content_item in content_items:
                                try:
                                    content_dict = content_item.dict() if hasattr(content_item, 'dict') else content_item
                                    video = await video_generator.create_full_video(
                                        content_dict, 
                                        platform, 
                                        with_voice=with_voice
                                    )
                                    # Сохраняем информацию о видео в БД
                                    video_data = video.to_dict()
                                    # Create a copy for database insertion to avoid ObjectId contamination
                                    db_video_data = video_data.copy()
                                    await db.videos.insert_one(db_video_data)
                                    total_videos += 1
                                except Exception as e:
                                    logging.error(f"❌ Ошибка создания видео для {platform}: {e}")
                    
                    logging.info(f"🎥 Создано {total_videos} видео")
                except Exception as e:
                    logging.error(f"❌ Ошибка генерации видео: {e}")
            
            # Публикуем Telegram контент
            telegram_content = content_batch.get("telegram", [])
            if telegram_content:
                logging.info("📤 Публикуем в Telegram...")
                
                # Убеждаемся что передаем правильные данные
                content_for_publishing = []
                for item in telegram_content:
                    if hasattr(item, 'dict'):
                        content_for_publishing.append(item.dict())
                    else:
                        content_for_publishing.append(item)
                
                published = await telegram_publisher.publish_batch(content_for_publishing, delay_seconds=30)
                
                if published:
                    publications_data = [post.dict() for post in published]
                    await db.publications.insert_many(publications_data)
                    
                logging.info(f"✅ Автоматизация с видео завершена: {len(published)} публикаций")
            else:
                logging.warning("❌ Не удалось сгенерировать Telegram контент")
        else:
            logging.warning("❌ Не удалось собрать тренды")
            
    except Exception as e:
        logging.error(f"❌ Ошибка полной автоматизации: {e}")

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("startup")
async def startup_event():
    logger.info("EKOSYSTEMA_FULL API запущен!")

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()