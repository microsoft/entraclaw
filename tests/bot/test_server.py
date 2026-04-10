"""Tests for bot server module."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from entraclaw.bot.server import EntraClawBot, create_bot_app


class TestEntraClawBot:
    """Tests for the EntraClaw bot activity handler."""

    @pytest.fixture
    def bot(self, tmp_path: object) -> EntraClawBot:
        return EntraClawBot()

    def test_bot_creation(self, bot: EntraClawBot) -> None:
        assert bot is not None

    @pytest.mark.asyncio
    async def test_on_message_writes_inbound(self, bot: EntraClawBot, tmp_path: object) -> None:
        """When bot receives a message, it writes to inbound.jsonl."""
        mock_activity = MagicMock()
        mock_activity.text = "hello from teams"
        mock_activity.id = "msg-123"
        mock_activity.timestamp = "2026-04-10T20:00:00Z"
        mock_activity.from_property = MagicMock()
        mock_activity.from_property.name = "Brandon"
        mock_activity.from_property.id = "user-456"
        mock_activity.from_property.aad_object_id = "aad-789"
        mock_activity.conversation = MagicMock()
        mock_activity.conversation.id = "conv-abc"

        mock_context = AsyncMock()
        mock_context.activity = mock_activity

        with patch("entraclaw.bot.server.write_inbound") as mock_write:
            await bot.on_message(mock_context)

        mock_write.assert_called_once()
        written = mock_write.call_args[0][0]
        assert written["content"] == "hello from teams"
        assert written["from"] == "Brandon"
        assert written["message_id"] == "msg-123"
        assert written["conversation_id"] == "conv-abc"

    @pytest.mark.asyncio
    async def test_on_message_skips_empty_text(self, bot: EntraClawBot) -> None:
        """Messages with no text (images, cards) are skipped."""
        mock_activity = MagicMock()
        mock_activity.text = None
        mock_activity.conversation = MagicMock()
        mock_activity.conversation.id = "conv-abc"

        mock_context = AsyncMock()
        mock_context.activity = mock_activity

        with patch("entraclaw.bot.server.write_inbound") as mock_write:
            await bot.on_message(mock_context)

        mock_write.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_members_added_saves_convo_ref(self, bot: EntraClawBot) -> None:
        """When bot is installed, conversation reference is saved."""
        mock_activity = MagicMock()
        mock_activity.conversation = MagicMock()
        mock_activity.conversation.id = "conv-new"
        mock_activity.recipient = MagicMock()
        mock_activity.recipient.id = "bot-id"

        mock_member = MagicMock()
        mock_member.id = "bot-id"

        mock_context = AsyncMock()
        mock_context.activity = mock_activity

        with patch("entraclaw.bot.server.save_reference") as mock_save:
            await bot.on_members_added(
                [mock_member],
                mock_context,
            )

        # Bot itself was added — should save convo ref
        mock_save.assert_called_once()


class TestCreateBotApp:
    """Tests for the aiohttp app factory."""

    def test_creates_app_with_routes(self) -> None:
        app = create_bot_app()
        routes = [
            r.resource.canonical
            for r in app.router.routes()
            if hasattr(r, "resource") and r.resource
        ]
        assert "/api/messages" in routes
