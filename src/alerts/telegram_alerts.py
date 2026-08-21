"""
Sends signal/trade/P&L alerts to Telegram with interactive Approve/Reject/Remind buttons.
Manual approval is a deliberate SEBI-compliance gate (see FYERS_FEASIBILITY_REPORT.md) —
even in paper trading, no order fires without an explicit tap.
"""
import asyncio
from datetime import datetime

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler
from src.utils.options_pricing import format_readable_contract


class TelegramAlertsManager:
    def __init__(self, bot_token: str, chat_id: str, logger=None):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.logger = logger
        self.bot = Bot(token=bot_token)
        self._decisions: dict[str, str] = {}
        self._app: Application | None = None

    async def start_listening(self) -> None:
        """Starts a background polling loop that records button taps into self._decisions."""
        if not self.bot_token or not self.chat_id:
            return
        try:
            self._app = Application.builder().token(self.bot_token).build()
            self._app.add_handler(CallbackQueryHandler(self._on_callback))
            await self._app.initialize()
            await self._app.start()
            await self._app.updater.start_polling()
        except Exception as e:
            if self.logger:
                self.logger.log_error(f"Telegram start_listening error: {e}")

    async def stop_listening(self) -> None:
        if self._app:
            try:
                await self._app.updater.stop()
                await self._app.stop()
                await self._app.shutdown()
            except Exception:
                pass

    async def _on_callback(self, update: Update, context) -> None:
        query = update.callback_query
        await query.answer()
        action, signal_id = query.data.split(":", 1)
        self._decisions[signal_id] = action
        await query.edit_message_reply_markup(reply_markup=None)

    async def send_signal_alert(self, signal) -> str:
        if not self.bot_token or not self.chat_id:
            return ""
        signal_id = f"{signal.strategy}_{signal.timestamp.strftime('%H%M%S')}"
        contract_name = format_readable_contract(signal.strike, timestamp=signal.timestamp)
        dir_emoji = "🟢" if signal.direction == "CE" else "🔴"
        text = (
            f"{dir_emoji} <b>SIGNAL GENERATED: {signal.strategy}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"• <b>Contract:</b> <code>{contract_name}</code>\n"
            f"• <b>Direction:</b> {'BULLISH' if signal.direction == 'CE' else 'BEARISH'} ({signal.direction})\n"
            f"• <b>Entry Price:</b> ₹{signal.entry_price:.2f}\n"
            f"• <b>Time:</b> {signal.timestamp.strftime('%H:%M:%S')} IST\n"
            f"• <b>Rationale:</b> {signal.rationale}"
        )
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ APPROVE", callback_data=f"approve:{signal_id}"),
            InlineKeyboardButton("❌ REJECT", callback_data=f"reject:{signal_id}"),
            InlineKeyboardButton("⏰ REMIND 5min", callback_data=f"remind:{signal_id}"),
        ]])
        try:
            await self.bot.send_message(chat_id=self.chat_id, text=text, parse_mode="HTML", reply_markup=keyboard)
        except Exception as e:
            if self.logger:
                self.logger.log_error(f"Telegram send_signal_alert failed: {e}")
        return signal_id

    async def await_decision(self, signal_id: str, timeout_secs: int = 300) -> str:
        elapsed = 0
        while elapsed < timeout_secs:
            if signal_id in self._decisions:
                return self._decisions.pop(signal_id)
            await asyncio.sleep(1)
            elapsed += 1
        return "timeout"

    async def send_trade_execution(self, order) -> None:
        if not self.bot_token or not self.chat_id:
            return
        contract_name = format_readable_contract(order.symbol, timestamp=order.entry_time)
        text = (
            f"🚀 <b>ORDER EXECUTED</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"• <b>Contract:</b> <code>{contract_name}</code>\n"
            f"• <b>Strategy:</b> {order.strategy}\n"
            f"• <b>Entry Price:</b> ₹{order.entry_price:.2f} (Qty: {order.qty * order.lot_size})\n"
            f"• <b>Stop-Loss:</b> ₹{order.stop_loss:.2f}\n"
            f"• <b>Target:</b> ₹{order.take_profit:.2f}\n"
            f"• <b>Status:</b> Position Active"
        )
        try:
            await self.bot.send_message(chat_id=self.chat_id, text=text, parse_mode="HTML")
        except Exception as e:
            if self.logger:
                self.logger.log_error(f"Telegram send_trade_execution failed: {e}")

    async def send_trailing_update(self, order, new_sl: float, stage_label: str) -> None:
        if not self.bot_token or not self.chat_id:
            return
        contract_name = format_readable_contract(order.symbol, timestamp=order.entry_time)
        text = (
            f"🔒 <b>TRAILING STOP-LOSS UPDATED ({stage_label})</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"• <b>Strategy:</b> {order.strategy}\n"
            f"• <b>Contract:</b> <code>{contract_name}</code>\n"
            f"• <b>New SL:</b> ₹{new_sl:.2f} (Entry: ₹{order.entry_price:.2f})\n"
            f"• <b>Protection:</b> Zero Capital Risk / Profit Locked"
        )
        try:
            await self.bot.send_message(chat_id=self.chat_id, text=text, parse_mode="HTML")
        except Exception as e:
            if self.logger:
                self.logger.log_error(f"Telegram send_trailing_update failed: {e}")

    async def send_position_exit(self, order, pnl: float, reason: str) -> None:
        if not self.bot_token or not self.chat_id:
            return
        contract_name = format_readable_contract(order.symbol, timestamp=order.entry_time)
        pnl_emoji = "💰" if pnl > 0 else "🛑"
        text = (
            f"{pnl_emoji} <b>POSITION CLOSED: {order.strategy}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"• <b>Contract:</b> <code>{contract_name}</code>\n"
            f"• <b>Exit Reason:</b> {reason}\n"
            f"• <b>Exit Price:</b> ₹{order.exit_price:.2f} (Entry: ₹{order.entry_price:.2f})\n"
            f"• <b>Realized P&L:</b> {'+' if pnl >= 0 else ''}₹{pnl:,.2f}"
        )
        try:
            await self.bot.send_message(chat_id=self.chat_id, text=text, parse_mode="HTML")
        except Exception as e:
            if self.logger:
                self.logger.log_error(f"Telegram send_position_exit failed: {e}")

    async def send_daily_summary(self, summary: dict) -> None:
        if not self.bot_token or not self.chat_id:
            return
        pnl = summary.get("realized_pnl", 0.0)
        pnl_icon = "📈" if pnl >= 0 else "📉"
        text = (
            f"{pnl_icon} <b>OPTIONS SIMULATOR DAILY SUMMARY</b>\n"
            f"📅 <b>Date:</b> {datetime.now().strftime('%d-%b-%Y')}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"• <b>Total Trades:</b> {summary.get('total_trades', 0)}\n"
            f"• <b>Win Rate:</b> {summary.get('win_rate', 0):.1f}%\n"
            f"• <b>Net Realized P&L:</b> {'+' if pnl >= 0 else ''}₹{pnl:,.2f}\n"
            f"• <b>Top Performer:</b> {summary.get('top_strategy', 'N/A')}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"✨ <i>Live simulation engine closed for the day.</i>"
        )
        try:
            await self.bot.send_message(chat_id=self.chat_id, text=text, parse_mode="HTML")
        except Exception as e:
            if self.logger:
                self.logger.log_error(f"Telegram send_daily_summary failed: {e}")
