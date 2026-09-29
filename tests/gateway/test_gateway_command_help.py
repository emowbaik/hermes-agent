"""Gateway command help rendering tests."""

import pytest

from gateway.config import Platform
from gateway.platforms.event import MessageEvent
from gateway.session import SessionSource


def _make_event(text: str, platform: Platform) -> MessageEvent:
    return MessageEvent(
        text=text,
        source=SessionSource(
            platform=platform,
            chat_id="chat-1",
            user_id="user-1",
            user_name="tester",
            chat_type="dm",
        ),
    )


def _make_runner():
    from gateway.run import GatewayRunner

    return object.__new__(GatewayRunner)


@pytest.mark.asyncio
async def test_help_sanitizes_slash_command_mentions_for_telegram(monkeypatch):
    """Telegram help output must not expose invalid uppercase/hyphenated slashes."""
    monkeypatch.setattr(
        "agent.skill_commands.get_skill_commands",
        lambda: {
            "/Linear": {"description": "Open Linear"},
            "/Custom-Thing": {"description": "Run a custom thing"},
        },
    )

    result = await _make_runner()._handle_help_command(
        _make_event("/help", Platform.TELEGRAM)
    )

    assert "`/linear`" in result
    assert "`/custom_thing`" in result
    assert "`/Linear`" not in result
    assert "`/Custom-Thing`" not in result


@pytest.mark.asyncio
async def test_commands_lists_builtins_without_skills(monkeypatch):
    """Telegram /commands lists built-in commands only — skill commands live in /skills."""
    monkeypatch.setattr(
        "agent.skill_commands.get_skill_commands",
        lambda: {"/Linear": {"description": "Open Linear"}},
    )

    result = await _make_runner()._handle_commands_command(
        _make_event("/commands 999", Platform.TELEGRAM)
    )

    assert "Skill Commands" not in result
    assert "`/Linear`" not in result
    assert "`/linear`" not in result


@pytest.mark.asyncio
async def test_skills_lists_skill_commands_sanitized_for_telegram(monkeypatch):
    """Telegram /skills listing uses Telegram-valid slash mentions, paginated under /skills."""
    monkeypatch.setattr(
        "agent.skill_commands.get_skill_commands",
        lambda: {
            "/Linear": {"description": "Open Linear"},
            "/Custom-Thing": {"description": "Run a custom thing"},
        },
    )

    result = await _make_runner()._handle_skills_command(
        _make_event("/skills", Platform.TELEGRAM)
    )

    assert "`/linear`" in result
    assert "`/custom_thing`" in result
    assert "`/Linear`" not in result
    assert "`/Custom-Thing`" not in result

    # Pagination is length-based (skill descriptions are long), so assert the nav
    # footer points at /skills whenever more than one page exists.
    many = {f"/Skill-{i}": {"description": "x" * 200} for i in range(40)}
    monkeypatch.setattr("agent.skill_commands.get_skill_commands", lambda: many)
    paged = await _make_runner()._handle_skills_command(_make_event("/skills", Platform.TELEGRAM))
    assert "/skills 2" in paged
    assert "/commands" not in paged

    # Every page must stay under Telegram's 4096-char cap after MarkdownV2 escaping,
    # which is what made the inline Prev/Next callback answer "Error loading page."
    from hermes_cli.slash_exec import CommandContext, execute_command
    first = execute_command("skills", CommandContext(surface="gateway", options={"page_size": 15}))
    for page_no in range(1, first.data["total_pages"] + 1):
        text = execute_command(
            "skills", CommandContext(surface="gateway", args=str(page_no), options={"page_size": 15})
        ).text
        assert len(text) < 4096, f"page {page_no} too long: {len(text)}"


