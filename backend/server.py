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

class ContentResponse(BaseModel):
    content: Dict[str, List[Dict]]
    videos: Optional[Dict[str, List[Dict]]] = None  # Информация о созданных видео
    total_items: int
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
    global trend_collector, content_generator, telegram_publisher, video_generator
    
    services = {
        "trend_collector": "active" if trend_collector else "inactive",
        "content_generator": "active" if content_generator else "inactive", 
        "telegram_publisher": "active" if telegram_publisher else "inactive",
        "video_generator": "active" if video_generator else "inactive"
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
    global content_generator, video_generator
    
    if not content_generator:
        content_generator = ContentGenerator(gemini_api_key=GEMINI_API_KEY)
    
    if request.generate_videos and not video_generator:
        video_generator = EnhancedVideoGenerator()
    
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
        
        # Сохраняем сгенерированный контент в БД
        all_content = []
        for platform, content_items in content_batch.items():
            content_data = [item.dict() for item in content_items]
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
                            video = await video_generator.create_full_video(
                                content_item.dict(), 
                                platform, 
                                with_voice=request.with_voice
                            )
                            # Сохраняем информацию о видео в БД
                            video_data = video.to_dict()
                            await db.videos.insert_one(video_data)
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
            formatted_content[platform] = [item.dict() for item in content_items]
        
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
                content_items.append(ContentItem(**content_doc))
        
        if not content_items:
            raise HTTPException(status_code=404, detail="Контент для публикации не найден")
        
        # Запускаем публикацию в фоне
        background_tasks.add_task(
            publish_content_background,
            content_items,
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

@api_router.get("/automation/run")
async def run_full_automation(background_tasks: BackgroundTasks):
    """Запуск полного цикла автоматизации"""
    background_tasks.add_task(full_automation_cycle)
    
    return {
        "message": "Запущен полный цикл автоматизации",
        "steps": ["Сбор трендов", "Генерация контента", "Публикация в Telegram"],
        "estimated_time": "5-10 минут"
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
async def publish_content_background(content_items: List[ContentItem], channel_key: str, delay_seconds: int):
    """Фоновая публикация контента"""
    global telegram_publisher
    
    try:
        published_posts = await telegram_publisher.publish_batch(content_items, channel_key, delay_seconds)
        
        # Сохраняем результаты публикации
        if published_posts:
            publications_data = [post.dict() for post in published_posts]
            await db.publications.insert_many(publications_data)
            
        logging.info(f"Фоновая публикация завершена: {len(published_posts)} постов")
        
    except Exception as e:
        logging.error(f"Ошибка фоновой публикации: {e}")

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