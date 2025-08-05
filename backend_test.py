#!/usr/bin/env python3
"""
EKOSYSTEMA_FULL Backend API Testing Suite
Tests all backend endpoints for the content automation system
"""
import asyncio
import aiohttp
import json
import logging
import sys
from datetime import datetime
from typing import Dict, List, Optional

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class EkosystemaAPITester:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        self.api_url = f"{self.base_url}/api"
        self.session = None
        self.test_results = {}
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=120),  # 2 minutes timeout for slow operations
            connector=aiohttp.TCPConnector(ssl=False)
        )
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def test_api_root(self) -> Dict:
        """Test API root endpoint"""
        logger.info("🔍 Testing API root endpoint...")
        try:
            async with self.session.get(f"{self.api_url}/") as response:
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"✅ API Root: {data}")
                    return {"status": "success", "data": data}
                else:
                    error_msg = f"API root returned status {response.status}"
                    logger.error(f"❌ {error_msg}")
                    return {"status": "error", "message": error_msg}
        except Exception as e:
            error_msg = f"API root test failed: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return {"status": "error", "message": error_msg}

    async def test_system_status(self) -> Dict:
        """Test system status endpoint"""
        logger.info("🔍 Testing system status endpoint...")
        try:
            async with self.session.get(f"{self.api_url}/status") as response:
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"✅ System Status: {data}")
                    
                    # Validate response structure
                    required_fields = ["status", "services"]
                    missing_fields = [field for field in required_fields if field not in data]
                    if missing_fields:
                        return {"status": "error", "message": f"Missing fields: {missing_fields}"}
                    
                    return {"status": "success", "data": data}
                else:
                    error_msg = f"Status endpoint returned status {response.status}"
                    logger.error(f"❌ {error_msg}")
                    return {"status": "error", "message": error_msg}
        except Exception as e:
            error_msg = f"System status test failed: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return {"status": "error", "message": error_msg}

    async def test_trends_collection(self) -> Dict:
        """Test trends collection endpoint"""
        logger.info("🔍 Testing trends collection endpoint...")
        logger.info("⏳ This may take 30-60 seconds due to external API calls...")
        
        try:
            async with self.session.get(f"{self.api_url}/trends") as response:
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"✅ Trends Collection: Found {data.get('total', 0)} trends")
                    
                    # Validate response structure
                    required_fields = ["trends", "total", "timestamp"]
                    missing_fields = [field for field in required_fields if field not in data]
                    if missing_fields:
                        return {"status": "error", "message": f"Missing fields: {missing_fields}"}
                    
                    # Check if trends data is valid
                    trends = data.get("trends", [])
                    if trends and len(trends) > 0:
                        # Validate first trend structure
                        first_trend = trends[0]
                        trend_fields = ["id", "title", "source", "url", "popularity_score", "keywords", "timestamp"]
                        missing_trend_fields = [field for field in trend_fields if field not in first_trend]
                        if missing_trend_fields:
                            return {"status": "error", "message": f"Missing trend fields: {missing_trend_fields}"}
                    
                    return {"status": "success", "data": data, "trend_ids": [t.get("id") for t in trends[:3]]}
                else:
                    error_text = await response.text()
                    error_msg = f"Trends endpoint returned status {response.status}: {error_text}"
                    logger.error(f"❌ {error_msg}")
                    return {"status": "error", "message": error_msg}
        except Exception as e:
            error_msg = f"Trends collection test failed: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return {"status": "error", "message": error_msg}

    async def test_content_generation(self, trend_ids: List[str]) -> Dict:
        """Test content generation endpoint - FOCUS ON GIFTS IN TELEGRAM"""
        logger.info("🔍 Testing content generation endpoint...")
        logger.info("🎁 SPECIAL TEST: Checking if content is about GIFTS IN TELEGRAM")
        logger.info("⏳ This may take 30-60 seconds due to LLM processing...")
        
        if not trend_ids:
            return {"status": "error", "message": "No trend IDs available for content generation"}
        
        try:
            payload = {
                "trend_ids": trend_ids[:2],  # Use first 2 trends to save time
                "platforms": ["telegram", "youtube_shorts"],
                "generate_videos": False,  # Test without videos first
                "monetize": True
            }
            
            async with self.session.post(
                f"{self.api_url}/content/generate",
                json=payload,
                headers={"Content-Type": "application/json"}
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"✅ Content Generation: Created {data.get('total_items', 0)} content items")
                    
                    # Validate response structure
                    required_fields = ["content", "total_items", "timestamp"]
                    missing_fields = [field for field in required_fields if field not in data]
                    if missing_fields:
                        return {"status": "error", "message": f"Missing fields: {missing_fields}"}
                    
                    # CRITICAL CHECK: Verify content is about gifts in Telegram
                    content = data.get("content", {})
                    telegram_content = content.get("telegram", [])
                    
                    gift_related_content = 0
                    for item in telegram_content:
                        text_content = item.get("text", "").lower()
                        title_content = item.get("title", "").lower()
                        
                        # Check for gift-related keywords
                        gift_keywords = ["подарок", "подарки", "gift", "gifts", "телеграм", "telegram", "бот", "bot"]
                        if any(keyword in text_content or keyword in title_content for keyword in gift_keywords):
                            gift_related_content += 1
                            logger.info(f"🎁 Found gift-related content: {item.get('title', 'No title')}")
                    
                    if gift_related_content == 0:
                        logger.warning("⚠️ WARNING: No content appears to be about gifts in Telegram!")
                        logger.warning("This matches user complaint about content not being about gifts in Telegram")
                    else:
                        logger.info(f"✅ Found {gift_related_content} gift-related content items")
                    
                    # Extract content IDs for publishing test
                    content_ids = []
                    for platform, items in content.items():
                        for item in items:
                            if item.get("id"):
                                content_ids.append(item["id"])
                    
                    return {
                        "status": "success", 
                        "data": data, 
                        "content_ids": content_ids,
                        "gift_related_count": gift_related_content,
                        "total_telegram_content": len(telegram_content)
                    }
                else:
                    error_text = await response.text()
                    error_msg = f"Content generation returned status {response.status}: {error_text}"
                    logger.error(f"❌ {error_msg}")
                    return {"status": "error", "message": error_msg}
        except Exception as e:
            error_msg = f"Content generation test failed: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return {"status": "error", "message": error_msg}

    async def test_telegram_publishing(self, content_ids: List[str]) -> Dict:
        """Test Telegram publishing endpoint"""
        logger.info("🔍 Testing Telegram publishing endpoint...")
        
        if not content_ids:
            return {"status": "error", "message": "No content IDs available for publishing"}
        
        try:
            payload = {
                "content_ids": content_ids[:1],  # Use only 1 content item
                "channel_key": "main",
                "delay_seconds": 5
            }
            
            async with self.session.post(
                f"{self.api_url}/publish/telegram",
                json=payload,
                headers={"Content-Type": "application/json"}
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"✅ Telegram Publishing: {data.get('message', 'Success')}")
                    
                    # Validate response structure
                    required_fields = ["message", "content_count"]
                    missing_fields = [field for field in required_fields if field not in data]
                    if missing_fields:
                        return {"status": "error", "message": f"Missing fields: {missing_fields}"}
                    
                    return {"status": "success", "data": data}
                else:
                    error_text = await response.text()
                    error_msg = f"Telegram publishing returned status {response.status}: {error_text}"
                    logger.error(f"❌ {error_msg}")
                    return {"status": "error", "message": error_msg}
        except Exception as e:
            error_msg = f"Telegram publishing test failed: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return {"status": "error", "message": error_msg}

    async def test_full_automation(self) -> Dict:
        """Test full automation endpoint - NEW FULL-CYCLE VERSION"""
        logger.info("🔍 Testing full automation endpoint...")
        logger.info("🤖 CRITICAL TEST: Testing /api/automation/full-cycle with video generation")
        logger.info("⏳ This starts a background process that may take several minutes...")
        
        try:
            # Test the new full-cycle endpoint with video generation
            params = {
                "generate_videos": "true",
                "monetize": "true", 
                "with_voice": "true"
            }
            
            async with self.session.post(
                f"{self.api_url}/automation/full-cycle",
                params=params
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"✅ Full Automation: {data.get('message', 'Started')}")
                    
                    # Validate response structure
                    required_fields = ["message", "steps", "features"]
                    missing_fields = [field for field in required_fields if field not in data]
                    if missing_fields:
                        return {"status": "error", "message": f"Missing fields: {missing_fields}"}
                    
                    # Check if video generation is enabled in response
                    features = data.get("features", {})
                    if not features.get("video_generation", False):
                        logger.warning("⚠️ WARNING: Video generation not enabled in full automation!")
                        logger.warning("This may explain user complaint about video generation not working")
                    
                    if not features.get("voice_synthesis", False):
                        logger.warning("⚠️ WARNING: Voice synthesis not enabled in full automation!")
                    
                    steps = data.get("steps", [])
                    video_step_found = any("видео" in step.lower() or "video" in step.lower() for step in steps)
                    if not video_step_found:
                        logger.warning("⚠️ WARNING: No video generation step found in automation steps!")
                    
                    logger.info(f"🎯 Automation steps: {steps}")
                    logger.info(f"🎬 Features enabled: {features}")
                    
                    return {"status": "success", "data": data}
                else:
                    error_text = await response.text()
                    error_msg = f"Full automation returned status {response.status}: {error_text}"
                    logger.error(f"❌ {error_msg}")
                    return {"status": "error", "message": error_msg}
        except Exception as e:
            error_msg = f"Full automation test failed: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return {"status": "error", "message": error_msg}

    async def test_video_generation_with_content(self, trend_ids: List[str]) -> Dict:
        """Test content generation WITH video generation enabled"""
        logger.info("🔍 Testing content generation WITH VIDEO GENERATION...")
        logger.info("🎬 CRITICAL TEST: Checking if videos are actually created")
        logger.info("⏳ This may take 2-3 minutes due to video processing...")
        
        if not trend_ids:
            return {"status": "error", "message": "No trend IDs available for video generation"}
        
        try:
            payload = {
                "trend_ids": trend_ids[:1],  # Use only 1 trend for video test
                "platforms": ["telegram", "youtube_shorts", "tiktok"],
                "generate_videos": True,  # CRITICAL: Enable video generation
                "with_voice": True,       # CRITICAL: Enable voice synthesis
                "monetize": False         # Disable monetization for faster testing
            }
            
            async with self.session.post(
                f"{self.api_url}/content/generate",
                json=payload,
                headers={"Content-Type": "application/json"}
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"✅ Content+Video Generation: Created {data.get('total_items', 0)} content items")
                    
                    # CRITICAL CHECK: Verify videos were created
                    videos_info = data.get("videos")
                    if videos_info is None:
                        logger.error("❌ CRITICAL: No videos field in response!")
                        return {"status": "error", "message": "Videos field missing from response - video generation failed"}
                    
                    if isinstance(videos_info, dict) and "error" in videos_info:
                        logger.error(f"❌ CRITICAL: Video generation error: {videos_info['error']}")
                        return {"status": "error", "message": f"Video generation failed: {videos_info['error']}"}
                    
                    total_videos = 0
                    video_platforms = []
                    
                    if isinstance(videos_info, dict):
                        for platform, platform_videos in videos_info.items():
                            if isinstance(platform_videos, list):
                                total_videos += len(platform_videos)
                                video_platforms.append(f"{platform}({len(platform_videos)})")
                                
                                # Check if video files actually exist
                                for video in platform_videos:
                                    video_path = video.get("file_path")
                                    if video_path:
                                        logger.info(f"🎬 Video created: {video_path}")
                                    else:
                                        logger.warning(f"⚠️ Video missing file_path: {video}")
                    
                    if total_videos == 0:
                        logger.error("❌ CRITICAL: No videos were created despite generate_videos=True!")
                        logger.error("This matches user complaint about video generation not working")
                        return {"status": "error", "message": "Video generation enabled but no videos created"}
                    else:
                        logger.info(f"✅ SUCCESS: Created {total_videos} videos across platforms: {', '.join(video_platforms)}")
                    
                    return {
                        "status": "success", 
                        "data": data,
                        "videos_created": total_videos,
                        "video_platforms": video_platforms
                    }
                else:
                    error_text = await response.text()
                    error_msg = f"Content+Video generation returned status {response.status}: {error_text}"
                    logger.error(f"❌ {error_msg}")
                    return {"status": "error", "message": error_msg}
        except Exception as e:
            error_msg = f"Content+Video generation test failed: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return {"status": "error", "message": error_msg}

    async def test_separate_video_generation(self, content_ids: List[str]) -> Dict:
        """Test separate video generation endpoint"""
        logger.info("🔍 Testing separate video generation endpoint...")
        logger.info("🎬 Testing /api/videos/generate endpoint specifically")
        
        if not content_ids:
            return {"status": "error", "message": "No content IDs available for video generation"}
        
        try:
            payload = {
                "content_ids": content_ids[:1],  # Use only 1 content item
                "platforms": ["youtube_shorts", "tiktok"],
                "with_voice": True,
                "voice_language": "ru"
            }
            
            async with self.session.post(
                f"{self.api_url}/videos/generate",
                json=payload,
                headers={"Content-Type": "application/json"}
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    total_videos = data.get("total_videos", 0)
                    logger.info(f"✅ Separate Video Generation: Created {total_videos} videos")
                    
                    # Validate response structure
                    required_fields = ["videos", "total_videos", "timestamp"]
                    missing_fields = [field for field in required_fields if field not in data]
                    if missing_fields:
                        return {"status": "error", "message": f"Missing fields: {missing_fields}"}
                    
                    if total_videos == 0:
                        logger.error("❌ CRITICAL: Separate video generation created 0 videos!")
                        return {"status": "error", "message": "Separate video generation failed - no videos created"}
                    
                    return {"status": "success", "data": data}
                else:
                    error_text = await response.text()
                    error_msg = f"Separate video generation returned status {response.status}: {error_text}"
                    logger.error(f"❌ {error_msg}")
                    return {"status": "error", "message": error_msg}
        except Exception as e:
            error_msg = f"Separate video generation test failed: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return {"status": "error", "message": error_msg}
        """Test dashboard statistics endpoint"""
        logger.info("🔍 Testing dashboard statistics endpoint...")
        
        try:
            async with self.session.get(f"{self.api_url}/stats/dashboard") as response:
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"✅ Dashboard Stats: {data.get('totals', {})}")
                    
                    # Validate response structure
                    required_fields = ["totals", "platform_stats", "last_updated"]
                    missing_fields = [field for field in required_fields if field not in data]
                    if missing_fields:
                        return {"status": "error", "message": f"Missing fields: {missing_fields}"}
                    
                    return {"status": "success", "data": data}
                else:
                    error_text = await response.text()
                    error_msg = f"Dashboard stats returned status {response.status}: {error_text}"
                    logger.error(f"❌ {error_msg}")
                    return {"status": "error", "message": error_msg}
        except Exception as e:
            error_msg = f"Dashboard stats test failed: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return {"status": "error", "message": error_msg}

    async def run_all_tests(self) -> Dict:
        """Run all API tests in logical order - ENHANCED FOR USER ISSUES"""
        logger.info("🚀 Starting EKOSYSTEMA_FULL Backend API Tests")
        logger.info("🎯 SPECIAL FOCUS: Testing user-reported issues with video generation and automation")
        logger.info(f"🌐 Testing API at: {self.api_url}")
        
        results = {
            "test_summary": {},
            "total_tests": 0,
            "passed_tests": 0,
            "failed_tests": 0,
            "test_details": {},
            "critical_issues": []
        }
        
        # Test sequence in logical order
        tests = [
            ("API Root", self.test_api_root),
            ("System Status", self.test_system_status),
            ("Trends Collection", self.test_trends_collection),
            ("Dashboard Stats", self.test_dashboard_stats),
        ]
        
        # Variables to pass data between tests
        trend_ids = []
        content_ids = []
        
        # Run basic tests first
        for test_name, test_func in tests:
            logger.info(f"\n{'='*50}")
            logger.info(f"Running: {test_name}")
            logger.info(f"{'='*50}")
            
            result = await test_func()
            results["test_details"][test_name] = result
            results["total_tests"] += 1
            
            if result["status"] == "success":
                results["passed_tests"] += 1
                results["test_summary"][test_name] = "✅ PASSED"
                
                # Extract data for dependent tests
                if test_name == "Trends Collection" and "trend_ids" in result:
                    trend_ids = result["trend_ids"]
            else:
                results["failed_tests"] += 1
                results["test_summary"][test_name] = f"❌ FAILED: {result.get('message', 'Unknown error')}"
                if test_name in ["API Root", "System Status", "Trends Collection"]:
                    results["critical_issues"].append(f"{test_name}: {result.get('message', 'Unknown error')}")
        
        # Run content generation (basic) if we have trends
        if trend_ids:
            logger.info(f"\n{'='*50}")
            logger.info("Running: Content Generation (Basic)")
            logger.info(f"{'='*50}")
            
            result = await self.test_content_generation(trend_ids)
            results["test_details"]["Content Generation (Basic)"] = result
            results["total_tests"] += 1
            
            if result["status"] == "success":
                results["passed_tests"] += 1
                results["test_summary"]["Content Generation (Basic)"] = "✅ PASSED"
                content_ids = result.get("content_ids", [])
                
                # Check for gift-related content issue
                gift_count = result.get("gift_related_count", 0)
                total_telegram = result.get("total_telegram_content", 0)
                if gift_count == 0 and total_telegram > 0:
                    results["critical_issues"].append("Content Generation: No gift-related content found in Telegram posts")
            else:
                results["failed_tests"] += 1
                results["test_summary"]["Content Generation (Basic)"] = f"❌ FAILED: {result.get('message', 'Unknown error')}"
                results["critical_issues"].append(f"Content Generation: {result.get('message', 'Unknown error')}")
        else:
            results["test_summary"]["Content Generation (Basic)"] = "⏭️ SKIPPED: No trends available"
        
        # CRITICAL TEST: Content generation WITH video generation
        if trend_ids:
            logger.info(f"\n{'='*50}")
            logger.info("Running: Content Generation WITH Videos (CRITICAL)")
            logger.info(f"{'='*50}")
            
            result = await self.test_video_generation_with_content(trend_ids)
            results["test_details"]["Content+Video Generation"] = result
            results["total_tests"] += 1
            
            if result["status"] == "success":
                results["passed_tests"] += 1
                results["test_summary"]["Content+Video Generation"] = "✅ PASSED"
                videos_created = result.get("videos_created", 0)
                if videos_created == 0:
                    results["critical_issues"].append("Video Generation: No videos created despite generate_videos=True")
            else:
                results["failed_tests"] += 1
                results["test_summary"]["Content+Video Generation"] = f"❌ FAILED: {result.get('message', 'Unknown error')}"
                results["critical_issues"].append(f"Video Generation: {result.get('message', 'Unknown error')}")
        else:
            results["test_summary"]["Content+Video Generation"] = "⏭️ SKIPPED: No trends available"
        
        # Test separate video generation endpoint if we have content
        if content_ids:
            logger.info(f"\n{'='*50}")
            logger.info("Running: Separate Video Generation")
            logger.info(f"{'='*50}")
            
            result = await self.test_separate_video_generation(content_ids)
            results["test_details"]["Separate Video Generation"] = result
            results["total_tests"] += 1
            
            if result["status"] == "success":
                results["passed_tests"] += 1
                results["test_summary"]["Separate Video Generation"] = "✅ PASSED"
            else:
                results["failed_tests"] += 1
                results["test_summary"]["Separate Video Generation"] = f"❌ FAILED: {result.get('message', 'Unknown error')}"
                results["critical_issues"].append(f"Separate Video Generation: {result.get('message', 'Unknown error')}")
        else:
            results["test_summary"]["Separate Video Generation"] = "⏭️ SKIPPED: No content available"
        
        # Run Telegram publishing if we have content
        if content_ids:
            logger.info(f"\n{'='*50}")
            logger.info("Running: Telegram Publishing")
            logger.info(f"{'='*50}")
            
            result = await self.test_telegram_publishing(content_ids)
            results["test_details"]["Telegram Publishing"] = result
            results["total_tests"] += 1
            
            if result["status"] == "success":
                results["passed_tests"] += 1
                results["test_summary"]["Telegram Publishing"] = "✅ PASSED"
            else:
                results["failed_tests"] += 1
                results["test_summary"]["Telegram Publishing"] = f"❌ FAILED: {result.get('message', 'Unknown error')}"
                results["critical_issues"].append(f"Telegram Publishing: {result.get('message', 'Unknown error')}")
        else:
            results["test_summary"]["Telegram Publishing"] = "⏭️ SKIPPED: No content available"
        
        # CRITICAL TEST: Full automation with videos
        logger.info(f"\n{'='*50}")
        logger.info("Running: Full Automation with Videos (CRITICAL)")
        logger.info(f"{'='*50}")
        
        result = await self.test_full_automation()
        results["test_details"]["Full Automation"] = result
        results["total_tests"] += 1
        
        if result["status"] == "success":
            results["passed_tests"] += 1
            results["test_summary"]["Full Automation"] = "✅ PASSED"
        else:
            results["failed_tests"] += 1
            results["test_summary"]["Full Automation"] = f"❌ FAILED: {result.get('message', 'Unknown error')}"
            results["critical_issues"].append(f"Full Automation: {result.get('message', 'Unknown error')}")
        
        return results

    def print_test_summary(self, results: Dict):
        """Print a formatted test summary with focus on user-reported issues"""
        logger.info(f"\n{'='*60}")
        logger.info("🎯 EKOSYSTEMA_FULL API TEST SUMMARY")
        logger.info("🚨 FOCUS: User-reported issues with video generation and automation")
        logger.info(f"{'='*60}")
        
        logger.info(f"📊 Total Tests: {results['total_tests']}")
        logger.info(f"✅ Passed: {results['passed_tests']}")
        logger.info(f"❌ Failed: {results['failed_tests']}")
        logger.info(f"📈 Success Rate: {(results['passed_tests']/results['total_tests']*100):.1f}%")
        
        logger.info(f"\n{'='*60}")
        logger.info("📋 DETAILED RESULTS")
        logger.info(f"{'='*60}")
        
        for test_name, status in results["test_summary"].items():
            logger.info(f"{test_name}: {status}")
        
        # Show critical issues that match user complaints
        critical_issues = results.get("critical_issues", [])
        if critical_issues:
            logger.info(f"\n{'='*60}")
            logger.info("🚨 CRITICAL ISSUES (MATCHING USER COMPLAINTS)")
            logger.info(f"{'='*60}")
            for issue in critical_issues:
                logger.error(f"❌ {issue}")
        
        # Show specific analysis for user complaints
        logger.info(f"\n{'='*60}")
        logger.info("🔍 USER COMPLAINT ANALYSIS")
        logger.info(f"{'='*60}")
        
        # Check video generation issues
        video_tests = ["Content+Video Generation", "Separate Video Generation"]
        video_issues = []
        for test_name in video_tests:
            if test_name in results["test_details"]:
                result = results["test_details"][test_name]
                if result["status"] == "error":
                    video_issues.append(f"{test_name}: {result.get('message', 'Unknown error')}")
        
        if video_issues:
            logger.error("🎬 VIDEO GENERATION ISSUES CONFIRMED:")
            for issue in video_issues:
                logger.error(f"   ❌ {issue}")
        else:
            logger.info("🎬 Video generation tests: PASSED")
        
        # Check automation issues
        if "Full Automation" in results["test_details"]:
            automation_result = results["test_details"]["Full Automation"]
            if automation_result["status"] == "error":
                logger.error(f"🤖 AUTOMATION ISSUES CONFIRMED: {automation_result.get('message', 'Unknown error')}")
            else:
                logger.info("🤖 Full automation test: PASSED")
        
        # Check content generation issues
        if "Content Generation (Basic)" in results["test_details"]:
            content_result = results["test_details"]["Content Generation (Basic)"]
            if content_result["status"] == "success":
                gift_count = content_result.get("gift_related_count", 0)
                if gift_count == 0:
                    logger.error("🎁 CONTENT ISSUE CONFIRMED: No gift-related content found in Telegram posts")
                else:
                    logger.info(f"🎁 Gift-related content: Found {gift_count} relevant posts")
            else:
                logger.error(f"🎁 CONTENT GENERATION FAILED: {content_result.get('message', 'Unknown error')}")


async def main():
    """Main test execution"""
    # Get backend URL from environment or use default
    import os
    
    # Read frontend .env to get backend URL
    frontend_env_path = "/app/frontend/.env"
    backend_url = "http://localhost:8001"  # fallback
    
    try:
        with open(frontend_env_path, 'r') as f:
            for line in f:
                if line.startswith('REACT_APP_BACKEND_URL='):
                    backend_url = line.split('=', 1)[1].strip()
                    break
    except Exception as e:
        logger.warning(f"Could not read frontend .env: {e}")
    
    logger.info(f"🌐 Using backend URL: {backend_url}")
    
    # Run tests
    async with EkosystemaAPITester(backend_url) as tester:
        results = await tester.run_all_tests()
        tester.print_test_summary(results)
        
        # Return exit code based on results
        if results["failed_tests"] > 0:
            logger.error("❌ Some tests failed!")
            return 1
        else:
            logger.info("✅ All tests passed!")
            return 0


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.info("🛑 Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"💥 Test execution failed: {e}")
        sys.exit(1)