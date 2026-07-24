import os
import json
import asyncio
import time
import platform
import sys
import discord
from discord.ext import commands
from discord import app_commands
from logger import log, Colors
import config
from discord_client import DiscordAPI, fetch_latest_build_number
from completer import QuestAutocompleter, get_progress_bar
from quest_utils import (
    _get,
    get_user_status,
    get_quest_name,
    get_task_type,
    is_completed,
    is_expired,
    is_enrolled,
    get_seconds_needed,
    get_seconds_done
)

try:
    import psutil
except ImportError:
    psutil = None

bot_start_time = time.time()

# Persistence for channel configuration
CONFIG_FILE = "channel.json"

def load_channel_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                data = json.load(f)
                config.CHANNEL_ID = data.get("channel_id")
                log(f"Đã tải cấu hình kênh hoạt động từ file: {config.CHANNEL_ID}", "ok")
        except Exception as e:
            log(f"Không thể tải cấu hình kênh: {e}", "warn")

def save_channel_config(channel_id):
    try:
        config.CHANNEL_ID = channel_id
        with open(CONFIG_FILE, "w") as f:
            json.dump({"channel_id": channel_id}, f)
        log(f"Đã lưu cấu hình kênh hoạt động mới: {channel_id}", "ok")
    except Exception as e:
        log(f"Không thể lưu cấu hình kênh: {e}", "error")


async def send_extension_guide(interaction: discord.Interaction):
    """Gửi hướng dẫn cài tiện ích và file zip tải về."""
    embed = discord.Embed(
        title="📦 Hướng Dẫn Cài Đặt Tiện Ích Lấy Token",
        color=discord.Color.from_rgb(88, 101, 242),
        description="""
**Bước 1 — Tải file tiện ích xuống**
📥 Nhấn nút **Tải Tiện Ích** ở bên trên để tải file `extension.zip`.

**Bước 2 — Mở trình quản lý Extension**
Trên trình duyệt Chrome/Edge, mở tab mới và truy cập:
`chrome://extensions`

**Bước 3 — Bật Chế độ Developer**
Góc trên bên phải, bật công tắc **Chế độ Nhà phát triển** (Developer mode) ✅

**Bước 4 — Cài đặt tiện ích**
Có 2 cách:
• Kéo thả trực tiếp file `extension.zip` vào trang
• Hoặc: Giải nén file zip →2 nhấn **Tải tiện ích chưa được đóng gói** (Load unpacked) →2 Chọn thư mục vừa giải nén

**Bước 5 — Dùng tiện ích**
1️⃣ Vào trang [discord.com](https://discord.com) và đăng nhập.
2️⃣ Nhấp vào icon tiện ích trên thanh công cụ trình duyệt → **Side Panel** sẽ hiện ra bên phải màn hình.
3️⃣ Bấm **Lấy & Sao Chép Token** — Token tự động được sao chép + hiện thông báo trực tiếp trên Discord!
4️⃣ Dán token vào nút **Bắt Đầu** 🚀 trong kênh này.
        """
    )
    embed.set_footer(text="Tiện ích chỉ đọc cookie tạm thời và không gửi dữ liệu ra bên ngoài. An toàn 100%.")
    
    # Gửi kèm file zip
    import os
    zip_path = os.path.join(os.path.dirname(__file__), "extension.zip")
    if os.path.exists(zip_path):
        file = discord.File(zip_path, filename="TXA_Discord_Token_Retriever.zip")
        await interaction.response.send_message(embed=embed, file=file, ephemeral=True)
    else:
        await interaction.response.send_message(embed=embed, ephemeral=True)


class DMProgressView(discord.ui.View):
    def __init__(self, completer=None):
        super().__init__(timeout=None)
        self.completer = completer

    @discord.ui.button(label="Dừng", style=discord.ButtonStyle.danger, emoji="🟥", custom_id="btn_stop_quest")
    async def stop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        if self.completer:
            await self.completer.stop()
            # The status_callback will handle updating the UI and disabling the button
            if self.completer.status_callback:
                await self.completer.status_callback("🛑 Đã dừng tiến trình.", finished=False)
            await interaction.followup.send("🛑 Đã dừng tiến trình làm quest của bạn.", ephemeral=True)

class TokenModal(discord.ui.Modal, title="🚀 Bắt đầu Quest Auto-Completer"):
    token_input = discord.ui.TextInput(
        label="Nhập Discord User Token của bạn:",
        placeholder="mfa.xxxx... hoặc Token chuẩn 3 phần (Tuyệt đối không chia sẻ cho người khác)",
        style=discord.TextStyle.long,
        min_length=50,
        required=True
    )

    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        # Immediate defer to avoid timeout
        await interaction.response.defer(ephemeral=True)

        completer = None
        import re
        user_token = self.token_input.value.strip().strip('"').strip("'").strip()
        if not user_token:
            await interaction.followup.send("❌ Token không được để trống!", ephemeral=True)
            return

        # Validate token format: MFA or Standard 3-part base64 token
        token_pattern = r"^(mfa\.[A-Za-z0-9_\-\=]+|[A-Za-z0-9_\-\=]+\.[A-Za-z0-9_\-\=]+\.[A-Za-z0-9_\-\=]+)$"
        if not re.match(token_pattern, user_token):
            await interaction.followup.send(
                "❌ **Định dạng Token không đúng quy chuẩn!**\n"
                "Discord User Token hợp lệ phải thuộc một trong hai dạng:\n"
                "1. Token chuẩn 3 phần cách nhau bằng dấu chấm (ví dụ: `MTI... .xxx... .yyy...`)\n"
                "2. Token MFA bắt đầu bằng `mfa.` (ví dụ: `mfa.xxx...`)\n"
                "Vui lòng copy chính xác token và thử lại!",
                ephemeral=True
            )
            return

        user_id = interaction.user.id
        username = interaction.user.name

        # Validate token
        api = DiscordAPI(user_token, getattr(config, 'BUILD_NUMBER', 504649))
        user_info = await api.validate_token()
        if not user_info:
            await interaction.followup.send(
                "❌ **Token không hợp lệ hoặc không thể kết nối tới Discord!**\n"
                "Vui lòng kiểm tra lại token của bạn hoặc lấy token mới theo hướng dẫn.",
                ephemeral=True
            )
            return

        # Check if already running for this user
        if user_id in config.ACTIVE_USERS:
            await interaction.followup.send("🔄 **Tài khoản của bạn đang chạy rồi!** Đang khởi động lại tiến trình mới...", ephemeral=True)
            try:
                # Stop existing completer
                old_info = config.ACTIVE_USERS[user_id]
                await old_info['completer'].stop()
                if old_info['task']:
                    old_info['task'].cancel()
            except Exception as e:
                log(f"Lỗi khi dừng luồng cũ: {e}", "warn")
            await asyncio.sleep(1)

        # Open DM Channel with the user
        try:
            dm_channel = await interaction.user.create_dm()
        except Exception as e:
            await interaction.followup.send(
                "❌ **Không thể gửi tin nhắn riêng cho bạn!**\n"
                "Vui lòng bật quyền nhận tin nhắn riêng (DM) từ thành viên máy chủ để nhận tiến độ.",
                ephemeral=True
            )
            return

        # Initialize view
        view = DMProgressView()

        # Send initial progress embed in DM
        start_ts = int(time.time())
        embed = discord.Embed(
            title="🎯 Auto-Quest",
            color=discord.Color.blue(),
            description=f"👤 **{user_info.get('username', username)}** · {config.EMOJI_LOADING} Đang kết nối · <t:{start_ts}:R>\n"
        )
        current_time = time.strftime("%H:%M %d/%m/%y")
        embed.set_footer(text=f"{current_time} | Quest Bot v4.0 • Built by TXA")
        try:
            dm_msg = await dm_channel.send(embed=embed, view=view)
        except Exception as e:
            await interaction.followup.send(
                "❌ **Không thể gửi DM cho bạn!** Vui lòng mở khóa DM từ người lạ trong cài đặt bảo mật.",
                ephemeral=True
            )
            return

        # Define status callback to edit the DM message
        async def status_callback(status_text: str, finished: bool = False, update_panel: bool = False):
            try:
                nonlocal dm_msg, view
                
                if update_panel:
                    await self.bot.update_control_panel()
                
                if status_text == "LIMIT_REACHED":
                    from payment_views import get_limit_embed_and_view
                    embed_edit, view_edit = get_limit_embed_and_view(user_id)
                    await dm_msg.edit(embed=embed_edit, view=view_edit)
                    return
                
                quests = []
                try:
                    if completer:
                        raw_quests = await completer.fetch_quests()
                        quests = [
                            q for q in raw_quests 
                            if (is_completed(q) or not is_expired(q)) 
                            and q.get("id") not in completer.failed_404_ids
                        ]
                except Exception:
                    pass
                
                # Auto-detect finished if all quests are completed
                if quests and all(is_completed(q) for q in quests):
                    finished = True
                
                if finished:
                    color = discord.Color.green()
                    completed_count = sum(1 for q in quests if is_completed(q)) if quests else 0
                    
                    # Disable stop button
                    for item in view.children:
                        if isinstance(item, discord.ui.Button) and item.custom_id == "btn_stop_quest":
                            item.disabled = True
                            
                    from limits_manager import get_user_total_completed
                    user_total = get_user_total_completed(user_id)
                    embed_edit = discord.Embed(
                        title="🎉 Hoàn thành tất cả Quest!",
                        color=color,
                        description=(
                            f"Đã hoàn thành **{completed_count} quest** trong phiên này 🏆\n"
                            f"🏆 **Tổng tất cả quest đã hoàn thành:** `{user_total}`\n"
                            "Phần thưởng sẽ xuất hiện trong mục **Quest** của Discord. Tận hưởng nhé!"
                        ),
                        timestamp=discord.utils.utcnow()
                    )
                    
                    user_avatar_url = interaction.user.display_avatar.url
                    embed_edit.set_author(name=user_info.get('username', username), icon_url=user_avatar_url)
                    
                    await dm_msg.edit(embed=embed_edit, view=view)
                    return
                    
                elif completer.stop_event.is_set():
                    status_str = "🛑 Đã dừng"
                    color = discord.Color.red()
                    # Disable stop button
                    for item in view.children:
                        if isinstance(item, discord.ui.Button) and item.custom_id == "btn_stop_quest":
                            item.disabled = True
                else:
                    status_str = f"{config.EMOJI_LOADING} Đang chạy"
                    color = discord.Color.blue()
                
                # Format description matching screenshot
                from limits_manager import get_user_total_completed
                user_total = get_user_total_completed(user_id)
                desc_lines = [
                    f"👤 **{user_info.get('username', username)}** · {status_str} · <t:{start_ts}:R>\n"
                    f"🏆 **Tổng quest đã hoàn thành:** `{user_total}` nhiệm vụ\n"
                ]
                
                if quests:
                    completed_count = sum(1 for q in quests if is_completed(q))
                    total_count = len(quests)
                    desc_lines.append(f"📋 **Nhiệm vụ ({completed_count}/{total_count} xong)**")
                    
                    for q in quests:
                        name = get_quest_name(q)
                        task = get_task_type(q) or "?"
                        qid = q.get("id")
                        
                        if is_completed(q):
                            desc_lines.append(f"{config.EMOJI_SUCCESS} ~~{name}~~")
                        elif completer and completer.current_quest_id == qid:
                            # This is the currently active quest! Show the live progress bar and ETA under it.
                            seconds_needed = get_seconds_needed(q)
                            seconds_done = get_seconds_done(q)
                            
                            remaining = max(0, int(seconds_needed - seconds_done))
                            if remaining >= 60:
                                eta_str = f"{remaining // 60}p {remaining % 60}s"
                            else:
                                eta_str = f"{remaining}s"
                                
                            bar = get_progress_bar(seconds_done, seconds_needed)
                            desc_lines.append(
                                f"{config.EMOJI_LOADING} **{name}** ({seconds_done:.0f}/{seconds_needed}s) - ⏳ Còn lại: {eta_str}\n"
                                f"└─ `{bar}`"
                            )
                        elif is_enrolled(q):
                            # Enrolled but waiting/queued (not the active one)
                            desc_lines.append(f"⚪ {name} `[{task}]` (Đang chờ)")
                        else:
                            # Not enrolled yet
                            desc_lines.append(f"⚪ {name} `[{task}]`")
                else:
                    desc_lines.append(status_text)
                
                embed_edit = discord.Embed(
                    title="🎯 Auto-Quest",
                    color=color,
                    description="\n".join(desc_lines)
                )
                
                cur_time = time.strftime("%H:%M %d/%m/%y")
                embed_edit.set_footer(text=f"{cur_time} | Quest Bot v4.0 • Built by TXA")
                
                await dm_msg.edit(embed=embed_edit, view=view)
            except Exception as e:
                log(f"Không thể cập nhật DM cho user {user_id}: {e}", "warn")

        # Initialize completer
        completer = QuestAutocompleter(api, user_id, status_callback=status_callback)
        view.completer = completer
        
        # Start in background task
        task = asyncio.create_task(completer.run())
        
        # Store metadata
        config.ACTIVE_USERS[user_id] = {
            'completer': completer,
            'task': task,
            'username': user_info.get('username', username),
            'start_timestamp': start_ts
        }

        # Ephemeral notification
        await interaction.followup.send(
            f"{config.EMOJI_SUCCESS} **Đăng nhập thành công tài khoản `{user_info.get('username')}`!**\n"
            f"📬 Tiến độ chi tiết đang được gửi vào tin nhắn riêng (DM) của bạn.",
            ephemeral=True
        )

        # Update main control panel stats
        await self.bot.update_control_panel()


class ControlView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None) # Persistent view
        self.bot = bot
        if config.EMOJI_ROCKET:
            self.start_button.emoji = config.EMOJI_ROCKET

    @discord.ui.button(label="Bắt Đầu", style=discord.ButtonStyle.success, emoji="🚀", custom_id="btn_start")
    async def start_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Only allow clicks in the configured channel
        if config.CHANNEL_ID and interaction.channel_id != config.CHANNEL_ID:
            await interaction.response.send_message("❌ Nút bấm này không thể sử dụng ở kênh này.", ephemeral=True)
            return
        
        modal = TokenModal(self.bot)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Hướng Dẫn", style=discord.ButtonStyle.secondary, emoji="❓", custom_id="btn_guide")
    async def guide_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if config.CHANNEL_ID and interaction.channel_id != config.CHANNEL_ID:
            await interaction.response.send_message("❌ Nút bấm này không thể sử dụng ở kênh này.", ephemeral=True)
            return
        
        await send_extension_guide(interaction)


async def cleanup_all_users():
    log(f"Đang dừng {len(config.ACTIVE_USERS)} tài khoản đang chạy ngầm...", "info")
    for uid, info in list(config.ACTIVE_USERS.items()):
        try:
            await info['completer'].stop()
            if info['task']:
                info['task'].cancel()
            log(f"  -> Đã dừng thành công luồng của {Colors.BOLD}{info['username']}{Colors.RESET}", "ok")
        except Exception as e:
            log(f"Lỗi khi dừng luồng của {uid}: {e}", "error")

class QuestBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        super().__init__(command_prefix="!", intents=intents)
        self.control_msg_id = None
        self.persistent_views_added = False

    async def close(self):
        log("Đang đóng các phiên hoạt động và dọn dẹp...", "info")
        await cleanup_all_users()
        await super().close()
        log("Hệ thống đã dừng hoàn toàn. Tạm biệt!", "ok")

    async def setup_hook(self):
        # Register persistent view
        self.add_view(ControlView(self))
        log("Đã tải view điều khiển persistent", "ok")

        # Fetch build number
        config.BUILD_NUMBER = await fetch_latest_build_number()

    async def on_ready(self):
        log(f"Bot đăng nhập thành công với tên: {Colors.BOLD}{self.user}{Colors.RESET}", "ok")
        
        # Load saved channel config
        load_channel_config()

        # Update/Create Control Panel in channel
        await self.update_control_panel()

        # Sync slash commands with Discord
        try:
            synced = await self.tree.sync()
            log(f"Đã sync {len(synced)} slash commands.", "ok")
        except Exception as e:
            log(f"Lỗi sync slash commands: {e}", "error")

    async def update_control_panel(self):
        """Creates or updates the main statistics control panel embed."""
        if not config.CHANNEL_ID:
            log("Chưa cấu hình CHANNEL_ID. Chờ admin sử dụng lệnh /channel.", "warn")
            return

        channel = self.get_channel(config.CHANNEL_ID)
        if not channel:
            try:
                channel = await self.fetch_channel(config.CHANNEL_ID)
            except Exception:
                log(f"Không tìm thấy kênh với ID {config.CHANNEL_ID}", "error")
                return

        # Prepare embed content exactly like the reference image
        embed = discord.Embed(
            title="🎯 Tự Động Hoàn Thành Quest Discord",
            description=(
                "Nhận **Nitro, avatar, profile decoration...** mà không cần thao tác thủ công.\n"
                "Nhấn 🚀 **Bắt Đầu** để nhập token — hệ thống sẽ tự **quét • nhận • hoàn thành** quest cho bạn."
            ),
            color=discord.Color.blue()
        )
        embed.set_author(name="TXA")
        
        # Status details in boxed codeblocks
        active_count = len(config.ACTIVE_USERS)
        embed.add_field(name="👤 Phiên hiện tại", value=f"```\n{active_count}\n```", inline=True)
        embed.add_field(name="⏳ Hàng chờ", value="```\n0\n```", inline=True)
        embed.add_field(name="▶️ Đang chạy", value=f"```\n{active_count}\n```", inline=True)
        embed.add_field(name="✅ Tổng quest đã hoàn thành", value=f"```\n{config.TOTAL_COMPLETED}\n```", inline=False)
        
        # Footer combining status and copyright
        current_time = time.strftime("%H:%M %d/%m/%y")
        embed.set_footer(text=f"Auto Scan • Auto Accept • Auto Complete • {current_time} | Quest Bot v4.0 - Built by TXA")

        # Try to find and edit the old message, or send a new one
        message_found = False
        if self.control_msg_id:
            try:
                msg = await channel.fetch_message(self.control_msg_id)
                await msg.edit(embed=embed, view=ControlView(self))
                message_found = True
            except Exception:
                pass

        if not message_found:
            # Clean old bot messages in the channel to prevent clutter
            try:
                async for msg in channel.history(limit=50):
                    if msg.author == self.user:
                        await msg.delete()
            except Exception as e:
                log(f"Lỗi dọn dẹp tin nhắn cũ: {e}", "warn")

            # Send fresh control panel
            try:
                new_msg = await channel.send(embed=embed, view=ControlView(self))
                self.control_msg_id = new_msg.id
            except Exception as e:
                log(f"Không thể gửi tin nhắn bảng điều khiển: {e}", "error")


bot = QuestBot()


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    log(f"Lỗi lệnh slash [{interaction.command.name if interaction.command else 'Unknown'}]: {error}", "error")
    
    if isinstance(error, app_commands.TransformerError):
        msg = f"❌ **Lỗi dữ liệu kênh/tham số:** `{error.value}` không phải là kênh hợp lệ hoặc không thể sử dụng cho lệnh này."
    else:
        msg = f"❌ **Có lỗi xảy ra khi thực hiện lệnh:** `{error}`"

    try:
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)
    except Exception as e:
        log(f"Không thể gửi thông báo lỗi tới user: {e}", "warn")


# Slash Command: Set up channel
@bot.tree.command(name="channel", description="[Admin] Cài đặt kênh hoạt động chính cho Bot và gửi Bảng điều khiển")
@app_commands.describe(target_channel="Kênh văn bản muốn đặt bảng điều khiển")
async def set_channel(interaction: discord.Interaction, target_channel: discord.abc.GuildChannel):
    # Verify Admin permission
    if interaction.user.id not in config.ADMIN_IDS:
        await interaction.response.send_message("❌ **Bạn không có quyền thực hiện lệnh này!** Chỉ Admin được cấu hình mới có quyền.", ephemeral=True)
        return

    # Check if target channel can receive messages
    if not hasattr(target_channel, "send") or isinstance(target_channel, discord.CategoryChannel):
        await interaction.response.send_message(
            f"❌ **Kênh `{target_channel.name}` không hỗ trợ gửi tin nhắn!** Vui lòng chọn một kênh văn bản (Text Channel).",
            ephemeral=True
        )
        return

    await interaction.response.defer(ephemeral=True)

    # Save to dynamic config
    save_channel_config(target_channel.id)

    # Recreate the control panel
    bot.control_msg_id = None
    await bot.update_control_panel()

    await interaction.followup.send(f"✅ **Đã thiết lập kênh hoạt động thành công tại:** {target_channel.mention}", ephemeral=True)


# Slash Command: Start/Join guide (slash command)
@bot.tree.command(name="start", description="Bắt đầu tự động làm quest hoặc hướng dẫn kênh hoạt động")
async def start_command(interaction: discord.Interaction):
    if not config.CHANNEL_ID:
        await interaction.response.send_message(
            "❌ **Cấu hình kênh hoạt động chưa được thiết lập!** Vui lòng liên hệ Admin để thiết lập bằng lệnh `/channel`.",
            ephemeral=True
        )
        return

    if interaction.channel_id == config.CHANNEL_ID:
        modal = TokenModal(bot)
        await interaction.response.send_modal(modal)
    else:
        await interaction.response.send_message(
            f"📢 **Để bắt đầu làm quest, vui lòng truy cập kênh hoạt động chính:** <#{config.CHANNEL_ID}>\n"
            f"Tại đó, bạn có thể nhấn nút **Bắt Đầu** 🚀 hoặc sử dụng lệnh `/start` để nhập token.",
            ephemeral=True
        )


# Command: Global status checker (slash command)
@bot.tree.command(name="status", description="[Admin] Xem danh sách người dùng đang chạy và trạng thái hệ thống")
async def show_status(interaction: discord.Interaction):
    if interaction.user.id not in config.ADMIN_IDS:
        await interaction.response.send_message("❌ **Bạn không có quyền thực hiện lệnh này!** Chỉ Admin được cấu hình mới có quyền.", ephemeral=True)
        return

    embed = discord.Embed(
        title="⚙️ Trạng thái hệ thống & Người dùng hoạt động",
        color=discord.Color.orange()
    )
    
    active_users = config.ACTIVE_USERS
    if not active_users:
        embed.description = "Không có tài khoản nào đang hoạt động."
    else:
        user_list = []
        for uid, info in active_users.items():
            run_time = int(time.time() - info['start_timestamp'])
            user_list.append(f"• <@{uid}> (`{info['username']}`, ID: `{uid}`) - Chạy từ <t:{info['start_timestamp']}:R> ({run_time}s trước)")
        embed.description = "\n".join(user_list)

    from limits_manager import load_limits, get_price_per_quest, get_transaction_timeout
    limits_data = load_limits()
    total_completed = limits_data.get("total_completed", config.TOTAL_COMPLETED)
    total_failed = limits_data.get("total_failed", config.TOTAL_FAILED)

    embed.add_field(name="✅ Thành công", value=f"`{total_completed}`", inline=True)
    embed.add_field(name="❌ Thất bại", value=f"`{total_failed}`", inline=True)
    embed.add_field(name="📦 Phiên bản", value="v4.0 (Async/Bot Mode)", inline=True)

    price = get_price_per_quest()
    timeout = get_transaction_timeout()
    channel_mention = f"<#{config.CHANNEL_ID}>" if config.CHANNEL_ID else "Chưa cấu hình"
    
    embed.add_field(name="📺 Kênh hoạt động", value=channel_mention, inline=True)
    embed.add_field(name="💰 Đơn giá quest", value=f"`{price:,} VNĐ`", inline=True)
    embed.add_field(name="⏳ Hạn thanh toán QR", value=f"`{timeout // 60} phút ({timeout}s)`", inline=True)

    await interaction.response.send_message(embed=embed, ephemeral=True)


# Slash Command: View detailed bot configuration (slash command for Admin)
@bot.tree.command(name="config", description="[Admin] Xem cấu hình chi tiết của hệ thống Bot")
async def view_config(interaction: discord.Interaction):
    if interaction.user.id not in config.ADMIN_IDS:
        await interaction.response.send_message("❌ **Bạn không có quyền thực hiện lệnh này!** Chỉ Admin được cấu hình mới có quyền.", ephemeral=True)
        return

    from limits_manager import get_price_per_quest, get_transaction_timeout
    price = get_price_per_quest()
    timeout = get_transaction_timeout()
    
    sepay_status = "Đã cấu hình ✅" if config.SEPAY_API_KEY else "Chưa cấu hình ❌"
    channel_mention = f"<#{config.CHANNEL_ID}>" if config.CHANNEL_ID else "Chưa cấu hình"
    
    embed = discord.Embed(
        title="⚙️ Bảng Cấu Hình Hệ Thống Quest Bot",
        color=discord.Color.blue(),
        timestamp=discord.utils.utcnow()
    )
    
    # Discord & Admin settings
    embed.add_field(name="📺 Kênh hoạt động", value=channel_mention, inline=True)
    embed.add_field(name="👑 Danh sách Admin IDs", value=f"`{', '.join(map(str, config.ADMIN_IDS))}`", inline=True)
    embed.add_field(name="🤖 Trạng thái Bot", value="Đang hoạt động 🟢", inline=True)

    # Quest settings
    embed.add_field(name="💰 Đơn giá quest", value=f"`{price:,} VNĐ`", inline=True)
    embed.add_field(name="⏳ Hạn thanh toán QR", value=f"`{timeout // 60} phút ({timeout}s)`", inline=True)
    embed.add_field(name="🔄 Tần suất quét quest", value=f"`{config.POLL_INTERVAL} giây`", inline=True)
    embed.add_field(name="💓 Tần suất Heartbeat", value=f"`{config.HEARTBEAT_INTERVAL} giây`", inline=True)
    embed.add_field(name="📥 Tự động nhận quest", value="Bật ✅" if config.AUTO_ACCEPT else "Tắt ❌", inline=True)
    
    # Payment settings
    embed.add_field(name="🏦 Ngân hàng", value=f"`{config.BANK_ID}`", inline=True)
    embed.add_field(name="🔢 Số tài khoản", value=f"`{config.ACCOUNT_NO}`", inline=True)
    embed.add_field(name="👤 Tên chủ tài khoản", value=f"`{config.ACCOUNT_NAME}`", inline=True)
    embed.add_field(name="🔑 Cổng thanh toán SePay", value=sepay_status, inline=False)
    
    embed.set_footer(text="Cấu hình chỉ hiển thị dạng Ephemeral dành riêng cho Admin.")
    await interaction.response.send_message(embed=embed, ephemeral=True)


# Command: Admin set quickly quest limits/balance (slash command for Admin)
@bot.tree.command(name="set_limit", description="[Admin] Đặt số lượt làm quest (số dư) cho người dùng")
@app_commands.describe(user_discord_id="ID Discord của người dùng muốn đặt giới hạn", balance="Số lượt quest muốn đặt (ví dụ: 5)")
async def set_limit_command(interaction: discord.Interaction, user_discord_id: str, balance: int):
    if interaction.user.id not in config.ADMIN_IDS:
        await interaction.response.send_message("❌ **Bạn không có quyền thực hiện lệnh này!** Chỉ Admin mới có quyền.", ephemeral=True)
        return

    if not user_discord_id.isdigit():
        await interaction.response.send_message("❌ ID người dùng không hợp lệ.", ephemeral=True)
        return

    if balance < 0:
        await interaction.response.send_message("❌ Số lượt phải lớn hơn hoặc bằng 0.", ephemeral=True)
        return

    from limits_manager import load_limits, save_limits
    uid = user_discord_id
    limits = load_limits()
    if uid not in limits:
        limits[uid] = {
            "free_completed_date": "",
            "free_completed_count": 0,
            "purchased_balance": 0,
            "total_completed": 0,
            "active_transaction": None
        }
    
    limits[uid]["purchased_balance"] = balance
    save_limits(limits)

    embed = discord.Embed(
        title="💳 Cập Nhật Giới Hạn Thành Công",
        color=discord.Color.green(),
        description=f"Đã cập nhật số dư lượt dùng cho người dùng <@{uid}> thành công."
    )
    embed.add_field(name="👤 Người dùng", value=f"<@{uid}> (ID: `{uid}`)", inline=True)
    embed.add_field(name="💎 Số dư mới", value=f"`{balance} lượt làm quest`", inline=True)
    embed.set_footer(text="Hệ thống quản lý giới hạn Quest Bot")

    await interaction.response.send_message(embed=embed, ephemeral=True)


# Command: Admin clear pycache and compile files (slash command for Admin)
@bot.tree.command(name="clear_cache", description="[Admin] Xóa sạch các thư mục __pycache__ và giải phóng dung lượng")
async def clear_cache_command(interaction: discord.Interaction):
    if interaction.user.id not in config.ADMIN_IDS:
        await interaction.response.send_message("❌ **Bạn không có quyền thực hiện lệnh này!** Chỉ Admin mới có quyền.", ephemeral=True)
        return

    import shutil
    deleted_files = 0
    deleted_dirs = 0
    total_size = 0
    root_dir = os.path.dirname(os.path.abspath(__file__))

    try:
        for root, dirs, files in os.walk(root_dir, topdown=False):
            for file in files:
                if file.endswith('.pyc') or file.endswith('.pyo'):
                    fp = os.path.join(root, file)
                    try:
                        total_size += os.path.getsize(fp)
                        os.remove(fp)
                        deleted_files += 1
                    except Exception:
                        pass
            for d in dirs:
                if d == '__pycache__':
                    dp = os.path.join(root, d)
                    try:
                        for r, ds, fs in os.walk(dp):
                            for f in fs:
                                total_size += os.path.getsize(os.path.join(r, f))
                        shutil.rmtree(dp)
                        deleted_dirs += 1
                    except Exception:
                        pass

        size_kb = total_size / 1024
        size_str = f"{size_kb:.2f} KB" if size_kb < 1024 else f"{size_kb / 1024:.2f} MB"

        embed = discord.Embed(
            title="🧹 Dọn Dẹp Bộ Nhớ Đệm Thành Công",
            color=discord.Color.green(),
            description="Đã xóa sạch bộ nhớ cache và các file biên dịch python tạm thời."
        )
        embed.add_field(name="📁 Số thư mục dọn dẹp", value=f"`{deleted_dirs} thư mục __pycache__`", inline=True)
        embed.add_field(name="📄 Số tệp tin đã xóa", value=f"`{deleted_files} tệp .pyc/.pyo`", inline=True)
        embed.add_field(name="💾 Dung lượng giải phóng", value=f"`{size_str}`", inline=False)
        embed.set_footer(text="Hệ thống dọn dẹp Quest Bot")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ Có lỗi xảy ra khi xóa cache: `{e}`", ephemeral=True)


# Command: Force stop a user (slash command)
@bot.tree.command(name="stop_user", description="[Admin] Dừng tiến trình tự động làm quest của một người dùng")
@app_commands.describe(user_discord_id="ID Discord của người dùng muốn dừng (ví dụ: 123456789)")
async def stop_user(interaction: discord.Interaction, user_discord_id: str):
    if interaction.user.id not in config.ADMIN_IDS:
        await interaction.response.send_message("❌ **Bạn không có quyền thực hiện lệnh này!**", ephemeral=True)
        return

    if not user_discord_id.isdigit():
        await interaction.response.send_message("❌ ID người dùng không hợp lệ.", ephemeral=True)
        return

    uid = int(user_discord_id)
    if uid not in config.ACTIVE_USERS:
        await interaction.response.send_message("❌ Người dùng này hiện không hoạt động.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    info = config.ACTIVE_USERS.pop(uid)
    try:
        await info['completer'].stop()
        if info['task']:
            info['task'].cancel()
        
        # Send a DM to that user informing them they were stopped
        user = bot.get_user(uid)
        if not user:
            user = await bot.fetch_user(uid)
        if user:
            await user.send("🛑 **Tiến trình làm quest của bạn đã bị dừng bởi quản trị viên.**")
    except Exception as e:
        log(f"Lỗi dừng user: {e}", "warn")

    await bot.update_control_panel()
    await interaction.followup.send(f"✅ **Đã dừng tiến trình hoạt động của:** {info['username']}", ephemeral=True)


class QuestClaimView(discord.ui.View):
    def __init__(self, completer, quest_choices, user_id):
        super().__init__(timeout=180)  # Timeout after 3 minutes
        self.completer = completer
        self.user_id = user_id

        # Dynamically add buttons for each unclaimed quest
        for quest_id, quest_name in quest_choices.items():
            button = discord.ui.Button(
                label=f"Nhận: {quest_name[:20]}",
                style=discord.ButtonStyle.primary,
                emoji="🎁",
                custom_id=f"claim_{quest_id}"
            )
            button.callback = self.make_callback(quest_id, quest_name)
            self.add_item(button)

    def make_callback(self, quest_id, quest_name):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.user_id:
                await interaction.response.send_message("❌ Nút bấm này không dành cho bạn.", ephemeral=True)
                return

            await interaction.response.defer(ephemeral=True)

            res = await self.completer.claim_reward(quest_id)
            if "error" in res:
                err_msg = res.get("details", res["error"])
                await interaction.followup.send(
                    f"❌ **Lỗi khi nhận thưởng từ Discord:**\n"
                    f"Nhiệm vụ: **{quest_name}**\n"
                    f"Chi tiết: `{err_msg}`\n"
                    f"Vui lòng thử lại sau.",
                    ephemeral=True
                )
            else:
                code = res.get("code")
                if code:
                    embed = discord.Embed(
                        title="🎉 Nhận Quà Thành Công!",
                        color=discord.Color.green(),
                        description=(
                            f"Nhiệm vụ: **{quest_name}**\n\n"
                            f"🔑 **Mã quà tặng (Promo Code):**\n"
                            f"```\n{code}\n```\n"
                            f"💡 *Sao chép mã trên và kích hoạt trong Gift Inventory hoặc trò chơi tương ứng.*"
                        )
                    )
                    await interaction.followup.send(embed=embed, ephemeral=True)
                else:
                    embed = discord.Embed(
                        title="🎉 Nhận Quà Thành Công!",
                        color=discord.Color.green(),
                        description=(
                            f"Nhiệm vụ: **{quest_name}**\n\n"
                            f"✨ *Phần thưởng đã được kích hoạt trực tiếp vào tài khoản của bạn!* (Trang trí hồ sơ/Khung đại diện)"
                        )
                    )
                    await interaction.followup.send(embed=embed, ephemeral=True)

                # Disable this button so it can't be clicked again
                for child in self.children:
                    if isinstance(child, discord.ui.Button) and child.custom_id == f"claim_{quest_id}":
                        child.disabled = True
                        child.label = f"Đã nhận: {quest_name[:15]}"
                        child.style = discord.ButtonStyle.secondary
                        break
                
                # Edit original message to show updated view
                try:
                    await interaction.message.edit(view=self)
                except Exception:
                    pass

        return callback


# Command: Help command (slash command)
@bot.tree.command(name="help", description="Xem hướng dẫn sử dụng và danh sách các lệnh của Bot")
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🤖 HƯỚNG DẪN SỬ DỤNG QUEST BOT 🤖",
        color=discord.Color.from_rgb(114, 137, 218),  # Discord Blurple
        description=(
            "Chào mừng bạn đến với **Quest Bot v4.0**! Hệ thống hỗ trợ tự động hóa "
            "quá trình làm Quest của Discord để nhận quà tặng cực kỳ tiện lợi.\n\n"
            "Để bắt đầu, hãy xem qua các lệnh có sẵn bên dưới."
        )
    )
    embed.add_field(
        name="👤 Lệnh Người Dùng (User Commands)",
        value=(
            "• **`/help`**: Hiển thị bảng hướng dẫn này.\n"
            "• **`/my_quests`**: Kiểm tra tiến độ và danh sách quest hiện tại của bạn. Đính kèm nút nhận mã quà tặng (Gift Code) khi quest hoàn thành.\n"
            "• **`/user_info`**: Xem thông tin tài khoản Discord đang chạy quest của bạn.\n"
            "• **`/stop_my_session`**: Dừng ngay lập trình chạy tự động của tài khoản của bạn."
        ),
        inline=False
    )
    embed.add_field(
        name="⚙️ Lệnh Quản Trị (Admin Commands)",
        value=(
            "• **`/channel`**: Thiết lập kênh hoạt động chính cho bot và tạo bảng điều khiển.\n"
            "• **`/status`**: Xem danh sách các phiên hoạt động và hiệu suất hệ thống.\n"
            "• **`/config`**: Xem chi tiết toàn bộ cấu hình hệ thống hiện tại của Bot.\n"
            "• **`/stop_user`**: Dừng phiên chạy của một người dùng thông qua ID Discord.\n"
            "• **`/system_stats`**: Xem chi tiết hiệu năng phần cứng máy chủ chạy bot."
        ),
        inline=False
    )
    embed.add_field(
        name="🚀 Hướng Dẫn Nhanh",
        value=(
            "1. Di chuyển đến kênh hoạt động được Admin thiết lập.\n"
            "2. Nhấn nút **Hướng Dẫn** ❓ → Tải file tiện ích `extension.zip` và cài vào Chrome/Edge (bật Developer mode, Load unpacked).\n"
            "3. Vào [discord.com](https://discord.com), bấm vào icon tiện ích → **Side Panel** hiện ra bên phải → Bấm **Lấy & Sao Chép Token**.\n"
            "4. Quay lại kênh này, nhấn nút **Bắt Đầu** 🚀 và dán Token vào.\n"
            "5. Bot sẽ gửi tin nhắn riêng (DM) cập nhật tiến độ. Dùng lệnh `/my_quests` để nhận Gift Code khi hoàn thành!"
        ),
        inline=False
    )
    embed.set_footer(text="Quest Bot v4.0 • Thiết kế bởi TXA")
    await interaction.response.send_message(embed=embed, ephemeral=True)


# Command: View active user quests (slash command)
@bot.tree.command(name="my_quests", description="Xem trạng thái các quest và nhận phần thưởng Gift Code")
async def my_quests(interaction: discord.Interaction):
    user_id = interaction.user.id
    if user_id not in config.ACTIVE_USERS:
        channel_mention = f"<#{config.CHANNEL_ID}>" if config.CHANNEL_ID else "bảng điều khiển chính"
        await interaction.response.send_message(
            f"❌ **Bạn hiện không có phiên hoạt động nào!**\n"
            f"Vui lòng nhấn nút **Bắt Đầu** ở {channel_mention} để nhập token.",
            ephemeral=True
        )
        return

    await interaction.response.defer(ephemeral=True)
    
    from limits_manager import is_user_limited
    if is_user_limited(user_id):
        from payment_views import get_limit_embed_and_view
        embed, view = get_limit_embed_and_view(user_id)
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)
        return

    info = config.ACTIVE_USERS[user_id]
    completer = info['completer']
    
    quests = await completer.fetch_quests()
    if not quests:
        await interaction.followup.send(
            "📭 **Không tìm thấy nhiệm vụ nào trong tài khoản của bạn.**",
            ephemeral=True
        )
        return

    # Filter quests to show active/completed
    active_quests = []
    for q in quests:
        qid = q.get("id")
        if qid not in completer.failed_404_ids and (is_completed(q) or not is_expired(q)):
            active_quests.append(q)

    if not active_quests:
        await interaction.followup.send(
            "💤 **Không có nhiệm vụ nào khả dụng hoặc chưa hết hạn trong tài khoản của bạn.**",
            ephemeral=True
        )
        return

    embed = discord.Embed(
        title="📋 Danh Sách Nhiệm Vụ Của Bạn",
        color=discord.Color.blue(),
        timestamp=discord.utils.utcnow()
    )
    embed.set_author(name=info['username'], icon_url=interaction.user.display_avatar.url)

    from limits_manager import get_user_total_completed
    user_total = get_user_total_completed(user_id)
    embed.add_field(name="🏆 Tổng quest đã hoàn thành của bạn", value=f"`{user_total}` nhiệm vụ", inline=False)

    desc_lines = []
    unclaimed_quests = {}  # maps qid -> name

    for q in active_quests:
        name = get_quest_name(q)
        task = get_task_type(q) or "?"
        qid = q.get("id")
        us = get_user_status(q)
        
        # Check claim status
        claimed = bool(_get(us, "claimedAt", "claimed_at"))
        
        if is_completed(q):
            if claimed:
                status_str = f"{config.EMOJI_SUCCESS} ~~{name}~~ `(Đã nhận quà)`"
            else:
                status_str = f"🎁 **{name}** `[Chờ nhận quà]`"
                unclaimed_quests[qid] = name
        elif completer.current_quest_id == qid:
            seconds_needed = get_seconds_needed(q)
            seconds_done = get_seconds_done(q)
            remaining = max(0, int(seconds_needed - seconds_done))
            eta_str = f"{remaining // 60}p {remaining % 60}s" if remaining >= 60 else f"{remaining}s"
            bar = get_progress_bar(seconds_done, seconds_needed)
            status_str = (
                f"{config.EMOJI_LOADING} **{name}** ({seconds_done:.0f}/{seconds_needed}s) - ⏳ Còn lại: {eta_str}\n"
                f"└─ `{bar}`"
            )
        elif is_enrolled(q):
            status_str = f"⚪ {name} `[{task}]` (Đang chờ)"
        else:
            status_str = f"⚪ {name} `[{task}]` (Chưa nhận)"
            
        desc_lines.append(status_str)

    embed.description = "\n".join(desc_lines)
    embed.set_footer(text="Giao diện cập nhật tự động · Built by TXA")

    if unclaimed_quests:
        view = QuestClaimView(completer, unclaimed_quests, user_id)
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)
    else:
        await interaction.followup.send(embed=embed, ephemeral=True)


# Command: View detailed active user Discord info (slash command)
@bot.tree.command(name="user_info", description="Xem chi tiết thông tin tài khoản Discord đang chạy")
async def user_info_command(interaction: discord.Interaction):
    user_id = interaction.user.id
    if user_id not in config.ACTIVE_USERS:
        channel_mention = f"<#{config.CHANNEL_ID}>" if config.CHANNEL_ID else "bảng điều khiển chính"
        await interaction.response.send_message(
            f"❌ **Bạn hiện không có phiên hoạt động nào!**\n"
            f"Vui lòng truy cập {channel_mention} để bắt đầu.",
            ephemeral=True
        )
        return

    await interaction.response.defer(ephemeral=True)
    info = config.ACTIVE_USERS[user_id]
    api = info['completer'].api

    r = await api.get("/users/@me")
    if r.status != 200:
        await interaction.followup.send(
            "❌ Không thể truy xuất thông tin tài khoản từ Discord API.",
            ephemeral=True
        )
        return

    user_data = await r.json()
    
    # Extract details
    username = user_data.get("username", "?")
    global_name = user_data.get("global_name") or "Không có"
    uid = user_data.get("id", "?")
    email = user_data.get("email") or "Không có"
    phone = user_data.get("phone") or "Không có"
    mfa = "Bật 🔐" if user_data.get("mfa_enabled") else "Tắt 🔓"
    locale = user_data.get("locale", "en-US")
    
    premium_type = user_data.get("premium_type", 0)
    nitro_map = {
        0: "Không ❌",
        1: "Nitro Classic 🎫",
        2: "Nitro Boost 🚀",
        3: "Nitro Basic 💎"
    }
    nitro_str = nitro_map.get(premium_type, "Không xác định")

    # Creation date from snowflake ID
    try:
        snowflake_time = int(uid) >> 22
        creation_timestamp = int((snowflake_time + 1420070400000) / 1000)
        creation_str = f"<t:{creation_timestamp}:R> (<t:{creation_timestamp}:F>)"
    except Exception:
        creation_str = "Không rõ"

    # Profile Avatar URL
    avatar_hash = user_data.get("avatar")
    if avatar_hash:
        avatar_url = f"https://cdn.discordapp.com/avatars/{uid}/{avatar_hash}.png?size=256"
    else:
        try:
            disc = int(user_data.get("discriminator", "0"))
            if disc == 0:
                avatar_index = (int(uid) >> 22) % 6
            else:
                avatar_index = disc % 5
        except Exception:
            avatar_index = 0
        avatar_url = f"https://cdn.discordapp.com/embed/avatars/{avatar_index}.png"

    embed = discord.Embed(
        title="👤 Thông Tin Tài Khoản Discord",
        color=discord.Color.from_rgb(32, 102, 168),
        timestamp=discord.utils.utcnow()
    )
    embed.set_author(name=f"{username} (@{global_name})", icon_url=avatar_url)
    embed.set_thumbnail(url=avatar_url)

    embed.add_field(name="🆔 User ID", value=f"`{uid}`", inline=True)
    embed.add_field(name="🌐 Quốc gia/Ngôn ngữ", value=f"`{locale}`", inline=True)
    embed.add_field(name="🔒 Bảo mật 2 lớp (MFA)", value=mfa, inline=True)
    
    embed.add_field(name="📧 Email", value=f"`{email}`", inline=True)
    embed.add_field(name="📞 Số điện thoại", value=f"`{phone}`", inline=True)
    embed.add_field(name="💎 Gói Nitro", value=nitro_str, inline=True)
    
    embed.add_field(name="📅 Ngày tạo tài khoản", value=creation_str, inline=False)
    
    embed.set_footer(text="Dữ liệu nhạy cảm chỉ hiển thị dạng Ephemeral cho bạn.")
    await interaction.followup.send(embed=embed, ephemeral=True)


# Command: View system stats (slash command)
@bot.tree.command(name="system_stats", description="Xem thông số kỹ thuật máy chủ và trạng thái bot")
async def system_stats(interaction: discord.Interaction):
    # Calculate Uptime
    uptime_seconds = int(time.time() - bot_start_time)
    uptime_days = uptime_seconds // 86400
    uptime_hours = (uptime_seconds % 86400) // 3600
    uptime_mins = (uptime_seconds % 3600) // 60
    uptime_secs = uptime_seconds % 60
    
    uptime_str = ""
    if uptime_days > 0:
        uptime_str += f"{uptime_days} ngày "
    if uptime_hours > 0 or uptime_days > 0:
        uptime_str += f"{uptime_hours} giờ "
    uptime_str += f"{uptime_mins} phút {uptime_secs} giây"

    # CPU and RAM Usage
    if psutil:
        try:
            cpu_usage = psutil.cpu_percent(interval=None)
            ram = psutil.virtual_memory()
            ram_usage = ram.percent
            ram_used_gb = ram.used / (1024 ** 3)
            ram_total_gb = ram.total / (1024 ** 3)
            ram_str = f"{ram_usage}% ({ram_used_gb:.1f} GB / {ram_total_gb:.1f} GB)"
        except Exception:
            cpu_usage = "N/A"
            ram_str = "N/A"
    else:
        cpu_usage = "Không khả dụng (Thiếu psutil)"
        ram_str = "Không khả dụng (Thiếu psutil)"

    embed = discord.Embed(
        title="🖥️ Trạng Thái Máy Chủ & Hiệu Suất Bot",
        color=discord.Color.dark_gray(),
        timestamp=discord.utils.utcnow()
    )
    embed.set_author(name=bot.user.name, icon_url=bot.user.display_avatar.url)

    # Bot metrics
    active_sessions = len(config.ACTIVE_USERS)
    from limits_manager import load_limits
    limits_data = load_limits()
    total_completed = limits_data.get("total_completed", config.TOTAL_COMPLETED)
    total_failed = limits_data.get("total_failed", config.TOTAL_FAILED)

    embed.add_field(name="🤖 Bot Uptime", value=f"`{uptime_str}`", inline=False)
    embed.add_field(name="👥 Phiên đang chạy", value=f"`{active_sessions} tài khoản`", inline=True)
    embed.add_field(name="✅ Quest Hoàn Thành", value=f"`{total_completed}`", inline=True)
    embed.add_field(name="❌ Quest Thất Bại", value=f"`{total_failed}`", inline=True)

    # Hardware metrics
    embed.add_field(name="🖥️ Hệ điều hành", value=f"`{platform.system()} {platform.release()}`", inline=False)
    embed.add_field(name="⚡ Tốc độ CPU", value=f"`{cpu_usage}%`", inline=True)
    embed.add_field(name="💾 Dung lượng RAM", value=f"`{ram_str}`", inline=True)
    embed.add_field(name="🐍 Phiên bản Python", value=f"`{platform.python_version()}`", inline=True)

    embed.set_footer(text="Quest Bot v4.0 • Thống kê hiệu năng phần cứng")
    await interaction.response.send_message(embed=embed)


# Command: Stop active session for calling user (slash command)
@bot.tree.command(name="stop_my_session", description="Dừng phiên làm quest tự động của bạn")
async def stop_my_session(interaction: discord.Interaction):
    user_id = interaction.user.id
    if user_id not in config.ACTIVE_USERS:
        channel_mention = f"<#{config.CHANNEL_ID}>" if config.CHANNEL_ID else "bảng điều khiển chính"
        await interaction.response.send_message(
            f"❌ **Tài khoản của bạn hiện không có phiên hoạt động nào đang chạy!**\n"
            f"Vui lòng truy cập {channel_mention} để bắt đầu.",
            ephemeral=True
        )
        return

    await interaction.response.defer(ephemeral=True)
    
    info = config.ACTIVE_USERS.pop(user_id)
    try:
        await info['completer'].stop()
        if info['task']:
            info['task'].cancel()
    except Exception as e:
        log(f"Lỗi khi người dùng tự dừng phiên: {e}", "warn")

    await bot.update_control_panel()
    await interaction.followup.send(
        "🛑 **Đã dừng thành công tiến trình làm quest tự động của bạn.**\n"
        "Tất cả tài nguyên đã được giải phóng.",
        ephemeral=True
    )


# Command: Admin test QR payment interface (slash command)
@bot.tree.command(name="qr_test", description="[Admin] Gửi giao diện thanh toán thử nghiệm (chọn dropdown để xem QR)")
async def qr_test(interaction: discord.Interaction):
    if interaction.user.id not in config.ADMIN_IDS:
        await interaction.response.send_message("❌ **Bạn không có quyền thực hiện lệnh này!** Chỉ Admin được cấu hình mới có quyền.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)
    
    # Clean previous transaction to allow repeated testing
    from limits_manager import cancel_transaction
    cancel_transaction(interaction.user.id)
    
    from payment_views import get_limit_embed_and_view
    embed, view = get_limit_embed_and_view(interaction.user.id)
    
    # Customize the embed description slightly for admin testing info
    embed.title = "🧪 [Thử nghiệm Admin] Giao Diện Mua Lượt Quest"
    embed.description = (
        "**Đây là giao diện mua lượt thử nghiệm dành riêng cho Admin.**\n"
        "Vui lòng chọn số lượng lượt muốn mua từ menu thả xuống bên dưới để tạo mã VietQR tương ứng."
    )
    
    await interaction.followup.send(embed=embed, view=view, ephemeral=True)


# Command: Admin set price per quest (slash command)
@bot.tree.command(name="set_price", description="[Admin] Đặt đơn giá cho mỗi lượt làm quest")
@app_commands.describe(price="Đơn giá mới cho mỗi lượt (ví dụ: 10000)")
async def set_price(interaction: discord.Interaction, price: int):
    if interaction.user.id not in config.ADMIN_IDS:
        await interaction.response.send_message("❌ **Bạn không có quyền thực hiện lệnh này!** Chỉ Admin được cấu hình mới có quyền.", ephemeral=True)
        return

    if price <= 0:
        await interaction.response.send_message("❌ Đơn giá phải lớn hơn 0.", ephemeral=True)
        return

    from limits_manager import set_price_per_quest
    set_price_per_quest(price)
    
    await interaction.response.send_message(
        f"✅ **Đã cập nhật đơn giá thành công!**\n"
        f"Đơn giá mới: **{price:,} VNĐ** cho mỗi lượt làm quest.",
        ephemeral=True
    )


# Command: Admin set transaction timeout (slash command)
@bot.tree.command(name="set_timeout", description="[Admin] Đặt thời gian hết hạn hóa đơn QR")
@app_commands.describe(minutes="Thời gian hết hạn tính bằng phút (ví dụ: 5)")
async def set_timeout(interaction: discord.Interaction, minutes: int):
    if interaction.user.id not in config.ADMIN_IDS:
        await interaction.response.send_message("❌ **Bạn không có quyền thực hiện lệnh này!** Chỉ Admin được cấu hình mới có quyền.", ephemeral=True)
        return

    if minutes <= 0:
        await interaction.response.send_message("❌ Thời gian hết hạn phải lớn hơn 0 phút.", ephemeral=True)
        return

    from limits_manager import set_transaction_timeout
    seconds = minutes * 60
    set_transaction_timeout(seconds)
    
    await interaction.response.send_message(
        f"✅ **Đã cập nhật thời hạn giao dịch thành công!**\n"
        f"Mã QR hóa đơn sẽ hết hạn sau: **{minutes} phút** ({seconds} giây).",
        ephemeral=True
    )


def run_bot():
    missing = []
    
    token = config.BOT_TOKEN.strip()
    if not token or "YOUR_DISCORD_BOT_TOKEN" in token or token == "":
        missing.append("BOT_TOKEN (Token của Discord Bot từ Discord Developer Portal)")
        
    if not config.ADMIN_IDS:
        missing.append("ADMIN_IDS (ID Discord tài khoản của bạn để phân quyền Admin)")

    if missing:
        log("=" * 65, "error")
        log("❌ CẤU HÌNH THIẾU HOẶC KHÔNG HỢP LỆ TRONG TỆP .env", "error")
        log("Vui lòng bổ sung đầy đủ các thông tin sau trước khi chạy:", "error")
        for item in missing:
            log(f"   👉 Thiếu: {item}", "error")
        log("💡 Hướng dẫn: Mở tệp `.env`, thay thế các giá trị mặc định bằng thông tin của bạn và lưu lại.", "info")
        log("=" * 65, "error")
        return
    
    banner = f"""{Colors.CYAN}{Colors.BOLD}
============================================================
       🤖 DISCORD QUEST AUTO-COMPLETER BOT v4.0 🤖
                🚀 Built by TXA 🚀
       Mã nguồn đã được tối ưu hóa bất đồng bộ
============================================================{Colors.RESET}"""
    print(banner)
    log("Đang khởi động Discord Bot...", "info")
    
    try:
        bot.run(config.BOT_TOKEN)
    except KeyboardInterrupt:
        log("Đã nhận tín hiệu Ctrl+C. Hệ thống đang tắt...", "warn")

if __name__ == "__main__":
    run_bot()
