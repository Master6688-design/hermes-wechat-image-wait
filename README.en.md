# tuwen-hefa (图文合发)

**Make your WeChat AI wait until you've sent all your pictures and said what you want, then answer once.** A Hermes plugin.

[中文](README.md)

## The problem

WeChat cannot send a picture and its caption as one message. You send the picture first, then type or speak your question. But the gateway hands the picture to the AI the moment it arrives, so the AI starts talking about the picture before your question is there, then gets interrupted and answers again.

This is not one AI's fault. Anything connected through WeChat's official ClawBot interface receives the picture and the words as two separate messages. This plugin fixes it for the Hermes WeChat gateway.

## What changes

| How you send | What the AI does |
|---|---|
| Picture first, then text or voice | On the first picture the gateway sends a short notice (below); when your words arrive, picture and words go to the AI together, one answer |
| Several pictures, then words | Notice sent once; all pictures plus your words, one answer |
| A question on its own first ("take a look at this"), then pictures | The question is already there: no notice, pictures go to the AI after about 4 seconds (time to collect several); that question covers only the next batch |
| Pictures and words already answered, then unrelated pictures | Treated as a new batch: notice, then wait for words |
| Only pictures, no words | Waits 1 minute after the last picture, then answers |
| Text only | Unchanged |

The notice is sent by the gateway itself, not by the AI. It is in Chinese by default; you can change it in `settings.json`:

> 图片已收到。请问还有图片要发吗？如有，请继续发送。
> 您告诉我想了解什么（文字或语音均可），我会立即作答；如未收到，我会在您最后一张图片发出 1 分钟后开始回复。
>
> (Pictures received. More to send? Go ahead. Tell me what you'd like to know, by text or voice, and I'll answer right away; if I hear nothing, I'll start replying 1 minute after your last picture.)

The AI never sees messages the gateway sends on its behalf, so when the batch is handed over the plugin adds one line saying what the gateway already told the user, and whether the user answered or the wait simply ran out. If the user replies "that's all", the AI knows what that answers.

## Install (about 5 minutes)

1. Put this repository's `tuwen-hefa` folder in `~/.hermes/plugins/`.
2. Back up `~/.hermes/config.yaml`, then add `- tuwen-hefa` to the `enabled:` list under `plugins:`.
3. Run `hermes gateway restart`. It waits for running replies to finish; pick a quiet moment.
4. In `~/.hermes/logs/`, look for:
   `tuwen-hefa: patch applied (wait 60s, after text 2s, follow-up 4s, notice on, skip none)`
   and `✓ weixin connected`.
5. On WeChat, try three ways: one picture then "that's all"; several pictures then a question; pictures only, waiting the full minute.

If you see `TARGETS MISSING` instead, your Hermes version doesn't match. The plugin changed nothing and WeChat works as before. Please open an issue with your version number.

## Uninstall

Remove that line from `enabled:` and restart the gateway.

## Settings (optional)

`settings.json` in the same folder. Write only what you change, then restart the gateway:

```json
{
  "image_wait_seconds": 60,
  "after_text_seconds": 2,
  "follow_up_seconds": 4,
  "recent_text_seconds": 90,
  "notice": "full notice text; an empty string sends no notice",
  "skip_profiles": ["a-profile-name"]
}
```

- `image_wait_seconds`: with pictures only, how long to wait after the last one. If you change it, change "1 分钟" in the notice too.
- `notice`: the notice text, in your own words and language.
- `after_text_seconds`: after the words arrive, how long to wait for anything that follows right behind.
- `follow_up_seconds`: after a question sent on its own, how long to collect the pictures.
- `recent_text_seconds`: how recent a stand-alone message must be to count as "the question is already here".
- `skip_profiles`: Hermes profiles listed here are left completely untouched.

## Voice

If WeChat's own transcription reaches Hermes as text, it counts as your question and is answered together with the pictures. Untranscribed voice: the plugin hands over the waiting pictures first (with a note that voice follows), then the voice is handled on its own. It works, in two rounds.

## How it works

Hermes's WeChat adapter (`gateway/platforms/weixin.py`) already batches text briefly before answering; pictures bypass that. The plugin routes pictures through the same batcher and stretches the wait to 1 minute when there are only pictures. It does not modify Hermes's source: when the gateway starts, it swaps a few of the adapter's methods in memory, so `hermes update` won't undo it. After each Hermes upgrade, check the log for `patch applied` or `TARGETS MISSING`.

## Limits

- Hermes WeChat gateway only. OpenClaw uses Tencent's official plugin; see Tencent/openclaw-weixin #359 and #362.
- Tested on Hermes 0.22.2, WeChat private chats. Group chats not tested.
- With pictures only, the reply comes 1 minute later. That is on purpose.

## Where it came from

tuwen-hefa comes from Manners Bespoke, a bespoke tailoring shop in Shenzhen. Its owner doesn't write code. He uses Hermes as his own AI assistant on WeChat, and wanted to set one up for his parents: older people tend to snap a photo of a lab report, then hold the button and say one sentence. The AI wouldn't wait for that sentence. On the evening of 26 October 2026 he and Claude Code fixed it at the gateway, tested it on a real phone over three rounds, fixed one bug, and settled the wording of the notice.

Upstream discussion: NousResearch/hermes-agent #83718.

— Manners Bespoke

## License

MIT. Use, change and share freely; keep the copyright notice.
