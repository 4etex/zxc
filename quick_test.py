#!/usr/bin/env python3
"""
Quick test for content generation issues
"""
import asyncio
import aiohttp
import json

async def test_content_generation():
    """Test basic content generation without videos"""
    base_url = "https://8a3b359c-000a-456c-a38a-303dee34fa3c.preview.emergentagent.com"
    api_url = f"{base_url}/api"
    
    async with aiohttp.ClientSession() as session:
        # First get some trends
        print("🔍 Getting trends...")
        async with session.get(f"{api_url}/trends") as response:
            if response.status == 200:
                trends_data = await response.json()
                trend_ids = [t["id"] for t in trends_data["trends"][:2]]
                print(f"✅ Got {len(trend_ids)} trend IDs: {trend_ids}")
            else:
                print(f"❌ Failed to get trends: {response.status}")
                return
        
        # Test content generation WITH videos
        print("\n🔍 Testing content generation WITH VIDEOS...")
        payload = {
            "trend_ids": trend_ids[:1],  # Use only 1 trend for video test
            "platforms": ["telegram", "youtube_shorts"],
            "generate_videos": True,
            "with_voice": True,
            "monetize": False
        }
        
        async with session.post(
            f"{api_url}/content/generate",
            json=payload,
            headers={"Content-Type": "application/json"}
        ) as response:
            print(f"Status: {response.status}")
            if response.status == 200:
                data = await response.json()
                print(f"✅ Content+Video generation successful!")
                print(f"Total items: {data.get('total_items', 0)}")
                
                # Check videos
                videos = data.get("videos")
                if videos:
                    print(f"Videos created: {videos}")
                    total_videos = sum(len(v) if isinstance(v, list) else 0 for v in videos.values())
                    print(f"Total videos: {total_videos}")
                else:
                    print("❌ No videos in response")
            else:
                error_text = await response.text()
                print(f"❌ Content+Video generation failed: {error_text}")

if __name__ == "__main__":
    asyncio.run(test_content_generation())