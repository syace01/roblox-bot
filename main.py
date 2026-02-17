"""
🎯 TRUE OMEGA BOT
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
import tempfile
import shutil
from threading import Thread

warnings.filterwarnings('ignore')

# Keep alive server
from flask import Flask
app = Flask(__name__)

@app.route('/')
def home():
    return "BOT ONLINE"

def run_flask():
    app.run(host='0.0.0.0', port=8080)

Thread(target=run_flask, daemon=True).start()

# Config
OWNER_ID = '1382137288502542339'
OCR_SPACE_KEY = 'K88183322888957'
TOKEN = os.environ.get('TOKEN')

if not TOKEN:
    print("❌ ERROR: TOKEN not found!")
    sys.exit(1)

print("=" * 50)
print("🎯 TRUE OMEGA BOT STARTING...")
print("=" * 50)

import discord
from discord import app_commands
import aiohttp

try:
    import yt_dlp
    YTDLP_OK = True
except:
    YTDLP_OK = False

class Downloader:
    def __init__(self):
        self.path = tempfile.mkdtemp()
    
    async def download(self, url, user_id):
        if not YTDLP_OK:
            return {"success": False, "error": "yt-dlp not installed"}
        
        dl_id = f"{user_id}_{int(time.time())}"
        output = os.path.join(self.path, f"{dl_id}.mp4")
        
        try:
            loop = asyncio.get_event_loop()
            def dl():
                ydl_opts = {
                    'format': 'best[ext=mp4][filesize<25M]',
                    'outtmpl': output,
                    'quiet': True,
                    'max_filesize': 25 * 1024 * 1024,
                }
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    return ydl.extract_info(url, download=True)
            
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
        return {"success": False, "error": "Unknown"}
    
    def cleanup(self, file_path):
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
        self.session = aiohttp.ClientSession()
        self.downloader = Downloader()
        
        @self.tree.command(name="scan", description="Scan Roblox username")
        async def scan(interaction: discord.Interaction, image: discord.Attachment, hint: str = None):
            await self.handle_scan(interaction, image, hint)
        
        @self.tree.command(name="download", description="Download video")
        async def download(interaction: discord.Interaction, url: str):
            await self.handle_download(interaction, url)
        
        await self.tree.sync()
        print("✅ Commands ready!")
    
    async def handle_scan(self, interaction, image, hint):
        if str(interaction.user.id) not in self.whitelist:
            await interaction.response.send_message("⛔ Not whitelisted", ephemeral=True)
            return
        
        await interaction.response.defer(thinking=True)
        
        try:
            async with self.session.get(image.url) as resp:
                img_data = await resp.read()
            
            b64 = base64.b64encode(img_data).decode()
            data = {
                'apikey': OCR_SPACE_KEY,
                'base64Image': f'data:image/jpeg;base64,{b64}',
                'OCREngine': '2',
                'scale': 'true',
            }
            
            async with self.session.post('https://api.ocr.space/parse/image', data=data, timeout=30) as resp:
                result = await resp.json()
                text = result.get('ParsedResults', [{}])[0].get('ParsedText', '')
            
            usernames = re.findall(r'@([A-Za-z0-9_]{3,20})\b', text)
            if not usernames:
                await interaction.followup.send("❌ No username found")
                return
            
            username = usernames[0]
            
            async with self.session.post(
                'https://users.roblox.com/v1/usernames/users',
                json={"usernames": [username], "excludeBannedUsers": False}
            ) as resp:
                data = await resp.json()
                if not data.get('data'):
                    await interaction.followup.send(f"❌ @{username} not found")
                    return
                user = data['data'][0]
            
            async with self.session.get(f'https://users.roblox.com/v1/users/{user["id"]}') as resp:
                profile = await resp.json()
            
            embed = discord.Embed(
                title=profile.get('displayName') or profile['name'],
                description=f"@{profile['name']}",
                url=f'https://roblox.com/users/{user["id"]}/profile',
                color=0x00D4AA
            )
            embed.add_field(name="ID", value=f"`{user['id']}`", inline=True)
            embed.add_field(name="Created", value=str(profile.get('created', 'Unknown'))[:10], inline=True)
            embed.set_image(url=image.url)
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            print(f"Error: {e}")
            await interaction.followup.send(f"❌ Error: {str(e)[:200]}")
    
    async def handle_download(self, interaction, url):
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
                await interaction.followup.send(f"❌ {result['error']}")
                return
            
            size_mb = result['size'] / (1024 * 1024)
            if result['size'] > 25 * 1024 * 1024:
                await interaction.followup.send(f"⚠️ File too large ({size_mb:.1f}MB)")
                self.downloader.cleanup(result['file_path'])
                return
            
            file = discord.File(result['file_path'], filename=f"{result['title'][:40]}.mp4")
            embed = discord.Embed(title="📥 Downloaded", description=result['title'][:100], color=0x00D4AA)
            embed.add_field(name="Size", value=f"{size_mb:.1f}MB")
            
            await interaction.followup.send(embed=embed, file=file)
            self.downloader.cleanup(result['file_path'])
            
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {str(e)[:200]}")
    
    async def on_ready(self):
        print(f"\n{'='*50}")
        print(f"✅ BOT ONLINE: {self.user}")
        print(f"{'='*50}\n")

def main():
    while True:
        try:
            bot = Bot()
            bot.run(TOKEN, log_handler=None)
            print("\n⚠️ Restarting in 5s...")
            time.sleep(5)
        except Exception as e:
            print(f"\n❌ Error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
