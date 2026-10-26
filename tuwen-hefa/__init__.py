"""tuwen-hefa（图文合发）: hold WeChat images until the instruction arrives.

WeChat cannot send a picture and its caption as one message, and upstream only
debounces TEXT, so the agent starts answering a lone image before the user has
typed (or spoken) what they want. This plugin routes PHOTO events through the
adapter's existing text batcher with a longer quiet period:

  * images alone          -> wait image_wait_seconds (default 60) after the last
                             image for more images or text
  * images + text arrived -> wait after_text_seconds (default 2), then answer together
  * images right after a text sent on its own (within recent_text_seconds)
                          -> the question already came; wait only follow_up_seconds
                             to collect a multi-page burst. That text is used up
                             by this batch; a caption already answered with an
                             earlier image never counts.
  * a voice note that Weixin did not transcribe arrives while images wait
                          -> images are flushed first, voice handled as usual

When a batch starts (and no question is already open) the gateway sends the user
`notice` once, so they know it is waiting. The agent never sees gateway-sent
messages, so the dispatched batch carries a line saying what was sent on its
behalf, and whether the user answered or the wait simply ran out.

Weixin-transcribed voice (see weixin-native-stt) arrives as TEXT, so it already
counts as the instruction. Settings live in settings.json next to this file;
profiles listed in skip_profiles keep upstream behaviour untouched.

Lives outside the hermes-agent git tree so `hermes update` cannot revert it.
If upstream renames a target, it logs a loud warning and changes nothing.
"""
from __future__ import annotations

import asyncio
import functools
import json
import logging
import time
from pathlib import Path

logger = logging.getLogger("tuwen_hefa")
_MARK = "_ec600_tuwen_hefa_patched"
_FLUSHED = "_iw_flushed"
_SHORT = "_iw_follow_up"
_NOTIFIED = "_iw_notified"
_VOICE = "_iw_voice_follows"

DEFAULTS = {
    "image_wait_seconds": 60.0,
    "after_text_seconds": 2.0,
    "follow_up_seconds": 4.0,
    "recent_text_seconds": 90.0,
    "notice": "图片已收到。请问还有图片要发吗？如有，请继续发送。\n"
              "您告诉我想了解什么（文字或语音均可），我会立即作答；"
              "如未收到，我会在您最后一张图片发出 1 分钟后开始回复。",
    "skip_profiles": [],
}


def _load_settings() -> dict:
    settings = dict(DEFAULTS)
    path = Path(__file__).with_name("settings.json")
    if path.exists():
        try:
            settings.update(json.loads(path.read_text(encoding="utf-8")))
        except Exception as exc:
            logger.warning("tuwen-hefa: settings.json unreadable, using defaults (%s)", exc)
    return settings


S = _load_settings()


def _has_image(event) -> bool:
    return any(str(m).startswith("image/") for m in (getattr(event, "media_types", None) or []))


def _profile_of(key: str) -> str:
    parts = key.split(":")
    return parts[1] if len(parts) > 1 and parts[0] == "agent" else ""


def _note_for(event) -> str:
    """What the gateway said on the agent's behalf, prefixed to the batch text."""
    head = f"[网关已代你向用户发送过这句话：「{S['notice']}」]"
    if (event.text or "").strip():
        return head
    if getattr(event, _VOICE, False):
        return f"{head}\n[用户随后发来一条语音，紧接着会单独送到你这里；请把这些图片和那条语音合起来理解。]"
    return (f"{head}\n[用户在最后一张图片后 {int(S['image_wait_seconds'])} 秒内没有再发图片或文字，"
            f"按上面的约定，现在开始回复。]")


def apply_patch() -> str:
    try:
        from gateway.platforms import weixin as wx
        from gateway.platforms.event import MessageType
    except Exception as exc:  # pragma: no cover
        return f"SKIP: cannot import weixin ({exc})"
    adapter = getattr(wx, "WeixinAdapter", None)
    if adapter is None:
        return "TARGETS MISSING (WeixinAdapter) - image wait NOT active"
    if getattr(adapter, _MARK, False):
        return "already patched"
    names = ("handle_message", "_text_batch_delay_for", "_dispatch_text_batch",
             "_text_batch_key", "_flush_text_batch_now", "send")
    orig = {n: getattr(adapter, n, None) for n in names}
    if not all(callable(f) for f in orig.values()):
        msg = "TARGETS MISSING (upstream refactor?) - image wait NOT active, images dispatch immediately"
        logger.warning("tuwen-hefa: %s", msg)
        return msg
    skip = set(S.get("skip_profiles") or [])

    def _last_text(self) -> dict:
        table = getattr(self, "_iw_last_text", None)
        if table is None:
            table = self._iw_last_text = {}
        return table

    async def _send_notice(self, event):
        try:
            result = await orig["send"](self, event.source.chat_id, S["notice"])
            ok = getattr(result, "success", True)
        except Exception as exc:
            ok = False
            logger.warning("tuwen-hefa: notice not sent (%s)", exc)
        setattr(event, _NOTIFIED, bool(ok))

    @functools.wraps(orig["handle_message"])
    async def handle_message(self, event):
        if not getattr(event, _FLUSHED, False):
            key = orig["_text_batch_key"](self, event)
            if _profile_of(key) not in skip:
                if event.message_type == MessageType.PHOTO and _has_image(event):
                    if key not in self._pending_text_batches:
                        since = time.monotonic() - _last_text(self).get(key, float("-inf"))
                        follow_up = since <= S["recent_text_seconds"]
                        setattr(event, _SHORT, follow_up)
                        if not follow_up and S["notice"]:
                            asyncio.create_task(_send_notice(self, event))
                    self._enqueue_text_event(event)
                    return
                if event.message_type == MessageType.VOICE and key in self._pending_text_batches:
                    setattr(self._pending_text_batches[key], _VOICE, True)
                    await orig["_flush_text_batch_now"](self, key)
        return await orig["handle_message"](self, event)

    @functools.wraps(orig["_text_batch_delay_for"])
    def _text_batch_delay_for(self, pending):
        base = orig["_text_batch_delay_for"](self, pending)
        if pending is None or not _has_image(pending):
            return base
        if (pending.text or "").strip():
            return max(base, S["after_text_seconds"])
        return max(base, S["follow_up_seconds"] if getattr(pending, _SHORT, False) else S["image_wait_seconds"])

    @functools.wraps(orig["_dispatch_text_batch"])
    async def _dispatch_text_batch(self, event):
        setattr(event, _FLUSHED, True)
        # Only a question sent on its own (no image) stays open for a follow-up image,
        # and the first image batch after it uses it up; a caption answered with its
        # image must not make the next unrelated image skip the wait.
        key = orig["_text_batch_key"](self, event)
        if _has_image(event):
            _last_text(self).pop(key, None)
            if getattr(event, _NOTIFIED, False):
                note = _note_for(event)
                event.text = f"{note}\n{event.text}" if (event.text or "").strip() else note
            logger.info("tuwen-hefa: dispatching %d image(s) with %d chars of text",
                        sum(1 for m in event.media_types if str(m).startswith("image/")), len(event.text or ""))
        elif event.message_type == MessageType.TEXT and (event.text or "").strip():
            _last_text(self)[key] = time.monotonic()
        return await orig["_dispatch_text_batch"](self, event)

    adapter.handle_message = handle_message
    adapter._text_batch_delay_for = _text_batch_delay_for
    adapter._dispatch_text_batch = _dispatch_text_batch
    setattr(adapter, _MARK, True)
    logger.info("tuwen-hefa: patch applied (wait %.0fs, after text %.0fs, follow-up %.0fs, notice %s, skip %s)",
                S["image_wait_seconds"], S["after_text_seconds"], S["follow_up_seconds"],
                "on" if S["notice"] else "off", sorted(skip) or "none")
    return "patched"


def register(ctx) -> None:
    logger.info("tuwen-hefa: %s", apply_patch())
