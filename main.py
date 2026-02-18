"""
🎯 TRUE OMEGA - NORTHFLANK VERSION
"""
import os
import sys
import asyncio
import json
import time
import re
import io
import base64
import warnings
import traceback
import tempfile
import shutil

warnings.filterwarnings('ignore')

# Config - USE ENVIRONMENT VARIABLES
OWNER_ID = os.getenv('OWNER_ID', '1382137288502542339')
OCR_SPACE_KEY = os.getenv('OCR_SPACE_KEY', 'K88183322888957')
TOKEN = os.getenv('DISCORD_TOKEN')  # MUST be set in Northflank!

if not TOKEN:
    print("❌ ERROR: DISCORD_TOKEN environment variable not set!")
    sys.exit(1)

print("=" * 60)
print("🎯 TRUE OMEGA BOT - NORTHFLANK")
print("=" * 60)

# Imports
try:
    import discord
    from discord import app_commands
    import aiohttp
    from PIL import Image
    print("✅ All imports successful")
except Exception as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)

# Check for yt-dlp
try:
    import yt_dlp
    YTDLP_AVAILABLE = True
    print("✅ yt-dlp available")
except:
    YTDLP_AVAILABLE = False
    print("⚠️ yt-dlp not available")

class VideoDownloader:
    def __init__(self):
        self.path = tempfile.mkdtemp()
    
    async def download(self, url: str, user_id: str) -> dict:
        if not YTDLP_AVAILABLE:
            return {"success": False, "error": "yt-dlp not installed"}
        
        dl_id = f"{user_id}_{int(time.time())}"
        output = os.path.join(self.path, f"{dl_id}.mp4")
        
        try:
            loop = asyncio.get_event_loop()
            
            def dl():
                ydl_opts = {
                    'format': 'best[ext=mp4][filesize<25M]/best[filesize<25M]',
                    'outtmpl': output,
                    'quiet': True,
                    'no_warnings': True,
                    'max_filesize': 25 * 1024 * 1024,
                }
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    return info
            
            result = await asyncio.wait_for(loop.run_in_executor(None, dl), timeout=120)
            
            files = [f for f in os.listdir(self.path) if f.startswith(dl_id)]
            if files:
                actual = os.path.join(self.path, files[0])
                return {
                    "success": True,
                    "file_path": actual,
                    "title": result.get('title', 'video') if isinstance(result, dict) else 'video',
                    "size": os.path.getsize(actual),
                }
        except Exception as e:
            return {"success": False, "error": str(e)[:100]}
        
        return {"success": False, "error": "Unknown error"}
    
    def cleanup(self, file_path: str):
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except:
            pass

class Bot(discord.Client):
    def __init__(self):
        super().__init__(
            intents=discord.Intents.all(),
            activity=discord.Activity(type=discord.ActivityType.watching, name="Roblox | /scan")
        )
        self.tree = app_commands.CommandTree(self)
        self.whitelist = {str(OWNER_ID)}
        self.session = None
        self.downloader = None
    
    async def setup_hook(self):
        print("🔧 Setting up...")
        
        # Load whitelist
        try:
            if os.path.exists('whitelist.json'):
                with open('whitelist.json', 'r') as f:
                    data = json.load(f)
                    self.whitelist.update(str(u) for u in data.get('users', []))
        except:
            pass
        
        self.session = aiohttp.ClientSession()
        self.downloader = VideoDownloader()
        
        @self.tree.command(name="scan", description="Scan Roblox username")
        async def scan(interaction: discord.Interaction, image: discord.Attachment, hint: str = None):
            await self.do_scan(interaction, image, hint)
        
        @self.tree.command(name="download", description="📥 Download video from URL")
        @app_commands.describe(url="Video URL to download")
        async def download(interaction: discord.Interaction, url: str):
            await self.do_download(interaction, url)
        
        await self.tree.sync()
        print("✅ Commands ready!")
    
    async def do_scan(self, interaction: discord.Interaction, image: discord.Attachment, hint: str):
        if str(interaction.user.id) not in self.whitelist:
            await interaction.response.send_message("⛔ Not whitelisted", ephemeral=True)
            return
        
        await interaction.response.defer(thinking=True)
        
        try:
            # Download image
            async with self.session.get(image.url) as resp:
                img_data = await resp.read()
            
            # OCR
            b64 = base64.b64encode(img_data).decode()
            data = {
                'apikey': OCR_SPACE_KEY,
                'base64Image': f'data:image/jpeg;base64,{b64}',
                'OCREngine': '2',
                'scale': 'true',
            }
            
            async with self.session.post('https://api.ocr.space/parse/image', data=data) as resp:
                result = await resp.json()
                text = result.get('ParsedResults', [{}])[0].get('ParsedText', '')
            
            # Find @username
            usernames = re.findall(r'@([A-Za-z0-9_]{3,20})\b', text)
            if not usernames:
                await interaction.followup.send(f"❌ No username found. OCR text: ```{text[:300]}```")
                return
            
            username = usernames[0]
            
            # Check Roblox
            async with self.session.post(
                'https://users.roblox.com/v1/usernames/users',
                json={"usernames": [username], "excludeBannedUsers": False}
            ) as resp:
                data = await resp.json()
                if not data.get('data'):
                    await interaction.followup.send(f"❌ @{username} not found on Roblox")
                    return
                user = data['data'][0]
            
            # Get profile
            async with self.session.get(f'https://users.roblox.com/v1/users/{user["id"]}') as resp:
                profile = await resp.json()
            
            # Result
            embed = discord.Embed(
                title=profile.get('displayName') or profile['name'],
                description=f"@{profile['name']}",
                url=f'https://roblox.com/users/{user["id"]}/profile',
                color=0x00D4AA
            )
            embed.add_field(name="ID", value=f"`{user['id']}`")
            embed.add_field(name="Created", value=str(profile.get('created', 'Unknown'))[:10])
            embed.set_image(url=image.url)
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            print(f"Error: {e}")
            traceback.print_exc()
            await interaction.followup.send(f"❌ Error: {str(e)[:200]}")
    
    async def do_download(self, interaction: discord.Interaction, url: str):
        if str(interaction.user.id) not in self.whitelist:
            await interaction.response.send_message("⛔ Not whitelisted", ephemeral=True)
            return
        
        if not url.startswith(('http://', 'https://')):
            await interaction.response.send_message("❌ Invalid URL", ephemeral=True)
            return
        
        await interaction.response.defer(thinking=True)
        
        try:
            result = await self.downloader.download(url, str(interaction.user.id))
            
            if not result['success']:
                await interaction.followup.send(f"❌ Download failed: {result['error']}")
                return
            
            size_mb = result['size'] / (1024 * 1024)
            if result['size'] > 25 * 1024 * 1024:
                await interaction.followup.send(f"⚠️ File too large ({size_mb:.1f}MB)")
                self.downloader.cleanup(result['file_path'])
                return
            
            file = discord.File(result['file_path'], filename=f"{result['title'][:40]}.mp4")
            
            embed = discord.Embed(
                title="📥 Download Complete",
                description=f"**{result['title'][:100]}**",
                color=0x00D4AA
            )
            embed.add_field(name="Size", value=f"{size_mb:.1f}MB", inline=True)
            
            await interaction.followup.send(embed=embed, file=file)
            self.downloader.cleanup(result['file_path'])
            
        except Exception as e:
            print(f"Download error: {e}")
            traceback.print_exc()
            await interaction.followup.send(f"❌ Error: {str(e)[:200]}")
    
    async def on_ready(self):
        print(f"\n✅ BOT ONLINE: {self.user}")
        print(f"   Servers: {len(self.guilds)}")
        print("=" * 60 + "\n")

def main():
    while True:
        try:
            bot = Bot()
            bot.run(TOKEN, log_handler=None)
            print("\n⚠️ Bot stopped, restarting...")
            time.sleep(5)
        except Exception as e:
            print(f"\n❌ Error: {e}")
            traceback.print_exc()
            print("\nRestarting in 5 seconds...")
            time.sleep(5)

if __name__ == "__main__":
    main()
