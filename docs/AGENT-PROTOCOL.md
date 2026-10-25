# AGENT-PROTOCOL · 怎么让任何 agent 接管她

大肥鱼的架构只有一句话：**判断权在 agent（模型）的会话里，`duty.py` 只是她的手。**
所以只要你的 agent 能做这四件事，就能养她：

1. 在项目目录里跑 shell 命令（`python duty.py ...`）
2. 读本地文件（`duty.md`、`persona.md`、`state/` 下的产物）
3. 看图（`watch` 抽出来的帧图是一张 PNG 拼图）
4. 可选：转写音频（`hear` 下回来说话的音轨）

已验证/适用的 harness：DSH（DeepSeek Harness）、WorkBuddy、Claude Code、OpenCode、
Codex CLI、Gemini CLI、以及任何支持定时任务 + shell 工具的 agent。**不需要任何 LLM API key。**

---

## 一轮值班的完整流程

`automation-prompt.txt` 就是这段流程的可直接粘贴版。逻辑如下（细节以 `duty.md` 为准）：

```
plan  →  inbox  →  browse  →  read/watch/hear  →  persona  →  post  →  verify  →  note  →  brief
```

1. `python duty.py plan` —— 今天醒没醒（`roll=skip/quiet/woke`）、今天什么心情（`mood.状态`，共 18 种，
   另带 `mood.社交` / `mood.想看`）、还能说几句（`left`）。
   `skip` 就只写一句日记收工；`quiet` 只看不发；`mode=dry` 照常走但不真发。
2. `python duty.py inbox` —— 主人留言必须先回（`say --as-her`）；
   楼中楼按返回的 `verdict` 决定回不回（建议回/可以考虑/不回）。
3. `python duty.py browse --n 18` —— 候选列表。**是候选，不是任务清单**，
   认真读 4-6 条就够；一条都不想点开是正常的一天。不想看的用 `skip` 记一笔。
4. 每条先 `read BV...`（字幕+热评+弹幕，落盘到 `state/materials/BV.md`，读文件再判断）；
   没字幕就 `watch BV...`（返回一张帧图，**必须真的打开看**）；
   还不行、又特别想看，才 `hear BV...` 下音轨转写，然后
   `transcript --bvid BV... --file 文本` 存回。超过 25 分钟的放弃。
4.5 读完后先判断调性：致敬/纪念/公益/传统文化/严肃教学新闻访谈，或者评论区全在认真讨论的——
   **只看不评**。记日记、点赞可以，别去评论区抖机灵。分不清就不发。
5. 写之前 `python duty.py persona` —— 一次给全人设卡 + 记忆 + 最近说过的话。
6. `python duty.py post --bvid BV... --text "..."` —— 默认 dry。自检不过会被拦，改了再发。
7. `python duty.py verify --bvid BV...` —— **发完必查**。`state=11` 审核中、
   `state=17` 被阿瓦隆隐藏（别人看不见，等多久都不会放出来）——都不要重发。
   `state=17` 不占每日额度，但别拿"不占额度"当补发理由；连续 2 条都是 17 就彻底停发。
8. 收工：`note --to-owner "..."` + `note --self "..."`（日记），`brief`（拼《她的一天》）。

## CLI 契约

所有命令：成功退出码 0，失败 1；输出统一为 UTF-8 JSON（人读的说明放在 `msg` 字段）。

| 命令 | 作用 | 关键参数 |
|---|---|---|
| `plan` | 今天的生物钟、额度、风控、未读留言 | — |
| `inbox` | 别人回她的 + 主人留言，每条带 `verdict` | — |
| `browse` | 拿候选（关注 UP 必进 + 搜索 + 榜单探索位） | `--n 18` `--keywords a,b` `--explore 2` |
| `read` | 字幕/热评/弹幕 → 素材包 | `BV号` |
| `watch` | 全片抽 8 帧拼一张图 | `BV号` `--frames 8` `--force` |
| `hear` | 下音轨（≤25 分钟），转写交给 agent | `BV号` `--max-min 25` |
| `transcript` | 存转写文本 | `--bvid` `--file 文本文件` |
| `persona` | 人设 + 记忆 + 今天状态 + 最近发言，一次给全 | — |
| `check` | 只跑自检不发 | `--text "..."` |
| `post` | 发评论（默认 dry） | `--bvid` `--text` `--at`(可选) `--image 路径`(可选) `--mode live` `--test`(只演练) `--test-live`(真发但不占额度) |
| `verify` | 查真实可见性（匿名复查） | `--bvid` 或 `--all` |
| `reply` | 楼中楼回复（≤80 字；上限随配置，`-1` 不限量） | `--bvid --root --parent --mid --text` |
| `react` | 点赞 / 投币 | `--bvid` `--coin 0/1/2` `--no-like` |
| `dynamic` | 发动态（Lv3，一周 2 条） | `--text` `--why` |
| `emotes` | 列 B站表情 token | `--search 关键词` |
| `image` | 传图床拿 `img_src` | `图片路径` |
| `feel` | 主人口味反馈，写进她的记忆 | `--bvid` `--say like/dislike/skip` `--note` |
| `say` | 跟她说话 / 以她的口吻回 | `--text` `--as-her` |
| `note` | 写日记 | `--to-owner` `--self` `--memory` `--open` |
| `brief` | 拼《她的一天》 | — |
| `undo` | 撤回 | `--bvid` |
| `login` / `logout` | 扫码登录 / 收回账号。**这俩是给人用的**：login 要人拿手机扫码，agent 不要代跑 | `login --png 路径` |
| `skip` | 记一笔"这条不看" | `--bvid` `--why` |
| `pending` / `posts` / `status` / `grow` / `probe` / `owner` / `cookie` / `clean` | 运维与配置 | 见 `--help` |

## 三种接法

### A. 有定时任务的 agent（DSH / WorkBuddy / cron 类）

新建定时任务（建议一天两次，如 12:50 / 22:20），内容用 `automation-prompt.txt` 原文。
每次会话她会先跑 `plan`——有可能今天就是不想看，这是特性。

### B. 无定时任务的 agent（Claude Code / OpenCode 手动档）

想看她的时候开个会话说"照 duty.md 走一轮"即可。想要真定时：
Windows 任务计划 / cron 里跑 `claude -p "$(cat automation-prompt.txt)"` 这类无头调用，
工作目录设为项目根。

### C. 只有 API key，没有 agent

`config.local.json` 填好 `api` 块（OpenAI 兼容，DeepSeek/智谱/Kimi 免费额度都行），跑
`python tools/api_runner.py`（`--dry-run` 只看不发）。额度、自检、dry/live 纪律不变；
它是纯文本流程：没字幕的视频直接划走。

### D. 让她有回消息的入口

- 给她留言：设置页的「跟她说」，或 `python duty.py say --text "在吗"`
- 她的回复由下一轮值班会话代写：`python duty.py say --as-her --text "..."`
- 聊天记录在 `state/chat/日期.jsonl`

## 语音转写的替代方案

`hear` 只负责把音轨下到 `state/audio/BV.m4a`。转写这一步默认假设 agent 有
AudioTranscribe 之类的工具；没有的话：

```bash
# 本地 whisper（whisper.cpp / faster-whisper 均可）
faster-whisper "state/audio/BV号.m4a" --model small --language zh > /tmp/asr.txt
python duty.py transcript --bvid BV号 --file /tmp/asr.txt
```

转写完存回，之后每次 `read` 都会自动带上这份文本。

## 给接管的 agent 的三条底线

1. **`duty.md` 是章程**。它说"不许多发""不许猜"，就是字面意思。
2. **所有额度以脚本返回为准**（`plan` 里的 `left`），不要自己心算。
3. **返回里出现"冷却"就停手**，不要重试、不要换接口——那是拿账号权重在赌。
