import discord
import time
import config
from limits_manager import (
    get_active_transaction,
    create_transaction,
    cancel_transaction,
    add_purchased_balance,
    verify_payment_on_sepay,
    get_price_per_quest,
    get_transaction_timeout
)

class QuestPurchaseDropdown(discord.ui.Select):
    def __init__(self, user_id):
        price = get_price_per_quest()
        options = [
            discord.SelectOption(label=f"1 Lượt Quest - {price:,}đ", value="1", emoji="💎", description="Mua lẻ 1 lượt làm quest tự động"),
            discord.SelectOption(label=f"2 Lượt Quest - {price*2:,}đ", value="2", emoji="🎫", description="Mua 2 lượt làm quest tự động"),
            discord.SelectOption(label=f"5 Lượt Quest - {price*5:,}đ", value="5", emoji="🔥", description="Tiết kiệm - Mua 5 lượt làm quest"),
            discord.SelectOption(label=f"10 Lượt Quest - {price*10:,}đ", value="10", emoji="👑", description="Gói lớn - Mua 10 lượt làm quest")
        ]
        super().__init__(placeholder="Chọn số lượng lượt quest muốn mua...", min_values=1, max_values=1, options=options)
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Menu này không dành cho bạn.", ephemeral=True)
            return

        # Edit the message immediately to show a loading state
        loading_embed = discord.Embed(
            title="⚙️ Đang Khởi Tạo Giao Dịch",
            color=discord.Color.blue(),
            description=f"{config.EMOJI_LOADING} Hệ thống đang tạo mã đơn hàng và VietQR, vui lòng đợi..."
        )
        self.disabled = True
        await interaction.response.edit_message(embed=loading_embed, view=None)

        quantity = int(self.values[0])
        
        # Create transaction
        tx = create_transaction(self.user_id, quantity)
        if not tx:
            await interaction.followup.send(
                "❌ **Bạn đang có một giao dịch chưa hoàn tất!**\n"
                "Vui lòng thanh toán giao dịch trước đó hoặc bấm nút **Hủy Giao Dịch** để tạo đơn mới.",
                ephemeral=True
            )
            # Re-edit the message back to selection screen
            embed, view = get_limit_embed_and_view(self.user_id)
            await interaction.edit_original_response(embed=embed, view=view)
            return

        # Pre-fetch VietQR image to ensure it is generated successfully and cached before updating UI
        import aiohttp
        order_id = tx["order_id"]
        amount = tx["amount"]
        qr_url = (
            f"https://img.vietqr.io/image/{config.BANK_ID}-{config.ACCOUNT_NO}-compact.png"
            f"?amount={amount}&addInfo={order_id}&accountName={config.ACCOUNT_NAME.replace(' ', '%20')}"
        )
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(qr_url, timeout=5) as r:
                    if r.status == 200:
                        await r.read()  # Download content to pre-warm cache
        except Exception:
            pass

        # Refresh message to show payment instructions and VietQR
        embed, view = get_limit_embed_and_view(self.user_id)
        await interaction.edit_original_response(embed=embed, view=view)


class QuestLimitPurchaseView(discord.ui.View):
    def __init__(self, user_id):
        super().__init__(timeout=300) # 5 minutes timeout
        self.add_item(QuestPurchaseDropdown(user_id))


class QuestPaymentConfirmView(discord.ui.View):
    def __init__(self, user_id, order_id, amount, quantity):
        super().__init__(timeout=300)
        self.user_id = user_id
        self.order_id = order_id
        self.amount = amount
        self.quantity = quantity

    @discord.ui.button(label="Xác Nhận Chuyển Khoản", style=discord.ButtonStyle.success, emoji="✅")
    async def confirm_payment(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Nút bấm này không dành cho bạn.", ephemeral=True)
            return

        # Check if transaction still exists and is not expired
        tx = get_active_transaction(self.user_id)
        if not tx or tx["order_id"] != self.order_id:
            embed, view = get_limit_embed_and_view(self.user_id)
            await interaction.response.edit_message(embed=embed, view=view)
            await interaction.followup.send(
                "❌ **Giao dịch đã hết hạn!**\n"
                "Mã QR này không còn hiệu lực. Vui lòng chọn số lượng để tạo đơn mới.",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)
        
        # Call SePay to verify
        is_paid = await verify_payment_on_sepay(self.order_id, self.amount)
        if is_paid:
            # Add balance
            add_purchased_balance(self.user_id, self.quantity)
            
            embed = discord.Embed(
                title="🎉 Thanh Toán Thành Công!",
                color=discord.Color.green(),
                description=(
                    f"Cảm ơn bạn! Đã nhận thành công số tiền **{self.amount:,} VNĐ**.\n"
                    f"Cộng thêm **+{self.quantity} lượt** làm quest tự động vào tài khoản.\n"
                    f"⚡ Tiến trình làm quest của bạn đã được kích hoạt chạy tiếp tự động!"
                )
            )
            embed.set_footer(text="Hệ thống tự động SePay • Cảm ơn quý khách")
            await interaction.response.edit_message(embed=embed, view=None)
            await interaction.followup.send("🎉 **Giao dịch hoàn tất!** Lượt quest đã được cập nhật.", ephemeral=True)
        else:
            await interaction.followup.send(
                f"❌ **Chưa nhận được thanh toán!**\n"
                f"Hệ thống SePay chưa quét thấy giao dịch chuyển khoản có nội dung: `{self.order_id}`.\n"
                f"Vui lòng đợi 1-2 phút sau khi chuyển tiền thành công rồi bấm lại nút **Xác Nhận**.",
                ephemeral=True
            )

    @discord.ui.button(label="Hủy Giao Dịch", style=discord.ButtonStyle.danger, emoji="❌")
    async def cancel_payment(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Nút bấm này không dành cho bạn.", ephemeral=True)
            return

        cancel_transaction(self.user_id)
        
        # Go back to selection screen
        embed, view = get_limit_embed_and_view(self.user_id)
        await interaction.response.edit_message(embed=embed, view=view)
        await interaction.followup.send("🛑 Đã hủy giao dịch hiện tại.", ephemeral=True)


def get_limit_embed_and_view(user_id: int):
    """Lấy Embed và View giao diện thanh toán hoặc giới hạn phù hợp cho user."""
    tx = get_active_transaction(user_id)
    
    if tx:
        # User has an active transaction: show payment QR and instructions
        order_id = tx["order_id"]
        amount = tx["amount"]
        quantity = tx["quests_to_buy"]
        created_at = tx["created_at"]
        timeout = get_transaction_timeout()
        expire_ts = created_at + timeout
        
        # Determine duration description: only show relative countdown if timeout is less than 1 hour
        if timeout < 3600:
            time_limit_str = f"<t:{expire_ts}:R> (vào lúc <t:{expire_ts}:T>)"
        else:
            time_limit_str = f"vào lúc <t:{expire_ts}:F>"
        
        # vietqr url generator
        qr_url = (
            f"https://img.vietqr.io/image/{config.BANK_ID}-{config.ACCOUNT_NO}-compact.png"
            f"?amount={amount}&addInfo={order_id}&accountName={config.ACCOUNT_NAME.replace(' ', '%20')}"
        )
        
        embed = discord.Embed(
            title="💳 Hóa Đơn Chuyển Khoản Mua Lượt Quest",
            color=discord.Color.gold(),
            description=(
                f"Vui lòng thực hiện chuyển khoản chính xác theo thông tin bên dưới.\n"
                f"Sử dụng App ngân hàng quét mã QR để điền tự động nội dung chuyển khoản.\n\n"
                f"⏳ **Thời hạn thanh toán:** {time_limit_str}\n\n"
                f"⚠️ **CẢNH BÁO QUAN TRỌNG:** Hệ thống đối soát hoàn toàn tự động. "
                f"Chúng tôi sẽ **KHÔNG chịu trách nhiệm** trong các trường hợp chuyển khoản sai nội dung chuyển khoản (`{order_id}`), sai số tiền hoặc sai thông tin tài khoản ngân hàng."
            )
        )
        embed.add_field(name="🏦 Ngân Hàng", value=f"**{config.BANK_ID}** (Ngân hàng Quân Đội)", inline=True)
        embed.add_field(name="🔢 Số Tài Khoản", value=f"`{config.ACCOUNT_NO}`", inline=True)
        embed.add_field(name="👤 Chủ Tài Khoản", value=f"`{config.ACCOUNT_NAME}`", inline=True)
        embed.add_field(name="💰 Số Tiền", value=f"`{amount}` VNĐ ({amount:,}đ)", inline=True)
        embed.add_field(name="📝 Nội Dung Chuyển Khoản", value=f"`{order_id}`", inline=True)
        embed.add_field(name="📦 Số Lượt Mua", value=f"**{quantity} lượt**", inline=True)
        
        embed.set_image(url=qr_url)
        embed.set_footer(text=f"⚠️ Lưu ý: Ghi đúng nội dung '{order_id}' để bot cộng lượt tự động.")
        
        view = QuestPaymentConfirmView(user_id, order_id, amount, quantity)
        return embed, view
    else:
        # No active transaction: show limit screen and purchase choices
        price = get_price_per_quest()
        embed = discord.Embed(
            title="⚠️ Giới Hạn Phiên Chạy Hàng Ngày",
            color=discord.Color.orange(),
            description=(
                "**Bạn đã hoàn thành 1 nhiệm vụ miễn phí hôm nay (1 quest/ngày).**\n\n"
                "Để tiếp tục làm tự động các quest còn lại, vui lòng nâng cấp bằng cách mua thêm lượt làm quest ở menu bên dưới.\n"
                f"🔹 **Đơn giá:** {price:,} VNĐ / 1 lượt làm quest.\n"
                "🔹 *Lượt mua sẽ không bị hết hạn và dùng được bất kỳ lúc nào.*"
            )
        )
        embed.set_footer(text="Hệ thống Quest Auto-Completer")
        
        view = QuestLimitPurchaseView(user_id)
        return embed, view
