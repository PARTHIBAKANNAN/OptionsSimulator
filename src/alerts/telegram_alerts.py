"""
Sends signal/trade/P&L alerts to Telegram with interactive Approve/Reject/Remind buttons.
Manual approval is a deliberate SEBI-compliance gate (see FYERS_FEASIBILITY_REPORT.md) —
even in paper trading, no order fires without an explicit tap.
"""
import asyncio
from datetime import datetime

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler


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
        self._app = Application.builder().token(self.bot_token).build()
        self._app.add_handler(CallbackQueryHandler(self._on_callback))
        await self._app.initialize()
        await self._app.start()
        await self._app.updater.start_polling()

    async def stop_listening(self) -> None:
        if self._app:
            await self._app.updater.stop()
            await self._app.stop()
            await self._app.shutdown()

    async def _on_callback(self, update: Update, context) -> None:
        query = update.callback_query
        await query.answer()
        action, signal_id = query.data.split(":", 1)
        self._decisions[signal_id] = action
        await query.edit_message_reply_markup(reply_markup=None)

    async def send_signal_alert(self, signal) -> str:
        signal_id = f"{signal.strategy}_{signal.timestamp.strftime('%H%M%S')}"
        text = (
            f"\U0001F680 SIGNAL GENERATED\n"
            f"――――――――――――――――――\n"
            f"Time: {signal.timestamp.strftime('%H:%M:%S')} IST\n"
            f"Strategy: {signal.strategy}\n"
            f"Direction: {'BULLISH' if signal.direction == 'CE' else 'BEARISH'} ({signal.direction})\n"
            f"Strike: {signal.strike}\n"
            f"Entry: Rs.{signal.entry_price:.2f}\n"
            f"Confidence: {signal.confidence * 100:.0f}%\n"
            f"Rationale: {signal.rationale}"
        )
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ APPROVE", callback_data=f"approve:{signal_id}"),
            InlineKeyboardButton("❌ REJECT", callback_data=f"reject:{signal_id}"),
            InlineKeyboardButton("⏰ REMIND 5min", callback_data=f"remind:{signal_id}"),
        ]])
        await self.bot.send_message(chat_id=self.chat_id, text=text, reply_markup=keyboard)
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
        text = (
            f"✅ ORDER EXECUTED\n"
            f"{order.symbol} | Qty: {order.qty} | Entry: Rs.{order.entry_price:.2f}\n"
            f"SL: Rs.{order.stop_loss:.2f} | TP: Rs.{order.take_profit:.2f}\n"
            f"Strategy: {order.strategy}"
        )
        await self.bot.send_message(chat_id=self.chat_id, text=text)

    async def send_position_update(self, positions: list, current_prices: dict) -> None:
        if not positions:
            return
        lines = ["\U0001F4C8 OPEN POSITIONS"]
        for p in positions:
            price = current_prices.get(p.symbol, p.entry_price)
            pnl = p.unrealized_pnl(price)
            lines.append(f"{p.symbol} | Entry: Rs.{p.entry_price:.2f} | Now: Rs.{price:.2f} | P&L: Rs.{pnl:,.0f}")
        await self.bot.send_message(chat_id=self.chat_id, text="\n".join(lines))

    async def send_daily_summary(self, summary: dict) -> None:
        text = (
            f"\U0001F4CA DAILY SUMMARY — {datetime.now().strftime('%Y-%m-%d')}\n"
            f"Trades: {summary.get('total_trades', 0)}\n"
            f"Win Rate: {summary.get('win_rate', 0):.1f}%\n"
            f"Realized P&L: Rs.{summary.get('realized_pnl', 0):,.2f}\n"
        )
        await self.bot.send_message(chat_id=self.chat_id, text=text)
