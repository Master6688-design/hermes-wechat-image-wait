# 图文合发（hermes-wechat-image-wait）

**让微信里的 AI 等你把图发完、把话说完，再一起回答。** 一个 Hermes 插件。

[English](README.en.md)

## 解决什么

微信不能把「图片＋文字」作为一条消息发出去，只能先发图、再打字或说语音。可接入 AI 的微信网关一收到图片就交给 AI，于是你要问的话还没打出来，AI 已经对着图开讲了；话到了，又被打断重答一遍。

这不是哪个 AI 的毛病。经微信官方 ClawBot 接口接 AI 的，图和字都是分两条到达的。本插件管的是 Hermes 的微信网关。

## 装上之后

| 你怎么发 | AI 怎么做 |
|---|---|
| 先发图，再打字或说语音 | 收到第一张图时回一句提示（见下），等你的话到了，图和话一起看，回一次 |
| 连发几张图，再说话 | 提示只发一次；几张图收齐，跟话一起看，回一次 |
| 先单独说「帮我看看这个」，再发图 | 问题已经有了，不发提示，图到后约 4 秒就看（留时间收齐多张）；这句话只管紧接着的那一批图 |
| 图和话已经一起回过，接着又发别的图 | 当作新的一批，照样提示、照样等你说话 |
| 只发图，什么都不说 | 最后一张图之后等 1 分钟，没等到话就开始看 |
| 只发文字 | 跟原来一样，不受影响 |

提示语由网关直接发出，不经过 AI：

> 图片已收到。请问还有图片要发吗？如有，请继续发送。
> 您告诉我想了解什么（文字或语音均可），我会立即作答；如未收到，我会在您最后一张图片发出 1 分钟后开始回复。

AI 看不到网关代发的话，所以插件把这批图交给 AI 时，会在前面附一行：网关已经代它说过这句提示，用户是回答了，还是到时间没说话。这样用户回一句「没有了」，AI 也知道是在回答什么。

## 安装（约 5 分钟）

1. 把本仓库的 `hermes-wechat-image-wait` 文件夹放到 `~/.hermes/plugins/` 下。
2. 先备份 `~/.hermes/config.yaml`，然后在 `plugins:` 下的 `enabled:` 列表里加一行 `- hermes-wechat-image-wait`。
3. 运行 `hermes gateway restart`。重启会等正在进行的回复说完再停，最好挑没人在聊的时候。
4. 到 `~/.hermes/logs/` 里找这一行，看到就是装好了：
   `hermes-wechat-image-wait: patch applied (wait 60s, after text 2s, follow-up 4s, notice on, skip none)`
   同时确认 `✓ weixin connected`。
5. 在微信上试三种发法：一张图后回一句「没有了」；几张图之后再打字；只发图不说话，等满 1 分钟。

看到的是 `TARGETS MISSING`：说明你的 Hermes 版本和插件对不上，插件什么都没改，微信照原样工作。欢迎开 issue 告诉我们版本号。

## 卸载

从 `enabled:` 列表删掉那一行，重启网关。

## 设置（可选）

同目录的 `settings.json`，只写要改的项，改后重启网关：

```json
{
  "image_wait_seconds": 60,
  "after_text_seconds": 2,
  "follow_up_seconds": 4,
  "recent_text_seconds": 90,
  "notice": "提示语全文；写成空字符串就不发提示",
  "skip_profiles": ["某个 profile 名"]
}
```

- `image_wait_seconds`：只有图时，最后一张图之后最多等多久。改了这个数，提示语里的「1 分钟」也要一起改。
- `notice`：提示语全文，可以换成你自己的口吻。
- `after_text_seconds`：话到之后再等多久，收齐紧跟着的图或话。
- `follow_up_seconds`：先单独提问、再发图时，等多久收齐多张。
- `recent_text_seconds`：多少秒内单独说过的话，算作「问题已经有了」。
- `skip_profiles`：列在这里的 Hermes profile 完全不受插件影响。

## 语音

微信自己转写好的语音如果以文字送到 Hermes，会当作你的问题，和图一起处理。微信没转写的语音：插件先把等着的图交给 AI（附注说明语音紧接着到），再单独处理语音，能用，只是分成两轮。

## 它是怎么做到的

Hermes 的微信接口（`gateway/platforms/weixin.py`）对文字本来就有「稍等再回」的合并机制，只是图片绕过了它。插件让图片也走这条通道，并把只有图时的等待拉长到 1 分钟。它不改 Hermes 的任何源码：网关启动时在内存里替换微信接口的几个方法，所以 `hermes update` 冲不掉它。每次升级 Hermes 后，看一眼日志里是 `patch applied` 还是 `TARGETS MISSING`。

## 限制

- 只支持 Hermes 的微信网关。OpenClaw 用的是腾讯官方插件，相关讨论见 Tencent/openclaw-weixin #359、#362。
- 测试环境：Hermes 0.22.2，微信私聊。群聊没有测过。
- 只有图、不说话时，回复会晚 1 分钟，这是有意的。

## 来历

图文合发出自 Manners Bespoke，深圳的一家定制西装店。店主不写代码，用 Hermes 在微信上接了自己的 AI 助理。他想给父母也搭一个：老人多半先拍一张化验单，再按住说一句话。可 AI 不等那句话。2026 年 10 月 26 日晚上，他和 Claude Code 一起从网关这一层把它修好，在微信上实测三轮，修掉一个漏洞，定了提示语。

上游相关讨论：NousResearch/hermes-agent #83718。

— Manners Bespoke

## 许可

MIT。可以自由使用、修改、转发，请保留版权声明。
