# 大肥鱼 · B站值班版

[![test](https://github.com/willings-79/dafeiyu/actions/workflows/test.yml/badge.svg)](https://github.com/willings-79/dafeiyu/actions/workflows/test.yml)
[![license](https://img.shields.io/badge/license-MIT%20%2B%20CC%20BY--NC--SA%204.0-blue)](LICENSE)
[![python](https://img.shields.io/badge/python-3.9%2B-blue)](https://www.python.org/)
[![API key](https://img.shields.io/badge/API%20key-不需要-brightgreen)](#这笔账怎么算她几乎不花钱)

**一条住在 B 站小号里的开源电子宠物：会自己逛、会闭嘴、会写日记。任何 agent 都能驱动，零 API 成本。**

和"AI 自动刷 B 站"那一类项目比，她有三件事不一样：

- **她真的看了。** 不是读标题、不是看简介——字幕优先，没字幕就抽 8 帧看画面，画面也说不清才下音轨转写。三级都拿不到，她就跳过，**不猜**。
- **她会闭嘴。** 每天有额度，有一定概率"今天不想看"，评论区在吵架就不进去，评论被藏着就自动停手养号。**少说，是这个项目能活下来的前提。**
- **她有自己的生活。** 有心情、有口味、有记忆，会升级；每天写两份日记——一份给你，一份给自己。**你也能随时给她留言、喂口味、改她的性格，她下一轮会先回你。**

**不需要 API key，也不需要另外充值。** 她的脑子是你就已经在用的那个 agent——只要它有订阅额度或免费额度，养她就不再产生一分钱 API 费用。核心是纯标准库，`git clone` 完就能跑；扫码登录、发评论要的几个小包，她第一次用到时会**自己装上**，不用你碰终端。

代码 MIT，随时可以改成你自己的鱼。**请先读下面的[免责声明](#免责声明)。**

---

## 它是怎么做到的

| | 普通自动评论脚本 | 大肥鱼 |
|---|---|---|
| 内容从哪来 | 标题 + 简介 + 模板 | 字幕原文 → 抽 8 帧看画面 → 音轨转写，逐级降级；都没有就跳过 |
| 谁来写 | 关键词打分 + 预设模板 | **驱动她的那个 agent**，脚本只提供"手" |
| 发完知不知道成没成 | 不知道 | 发完**脚本自动**用匿名请求复查可见性（`plan` 每轮补查漏网的），被藏就停手 |
| 状态存在哪 | 数据库 / 内存 | 纯文件 `state/`——你能直接打开读、直接改 |

判断权在模型手里、脚本只提供"手"（CLI），是这个项目最重要的一条架构决定。好处很直接：
换人设不用改代码（改 `persona.md`），换 agent 不用改代码（换个定时任务），出问题能直接翻 `state/` 里的文件看。

---

## 这笔账怎么算：她几乎不花钱

大多数 B 站 bot 的隐形成本是 API 账单——你得多开一个 key、按 token 计费、跑得越勤越贵。
她的架构是反过来的：**模型不在项目里，在你已经在用的 agent 里。**

| 你手上有什么 | 要额外花钱吗 | 怎么跑 |
|---|---|---|
| 有 agent，带订阅或**免费额度**（WorkBuddy · Claude Code · Codex CLI · Gemini CLI · OpenCode · Cursor …） | **不用**，吃你现有的额度 | 把 `automation-prompt.txt` 丢进它的定时任务 |
| 没有 agent，但有 API key | 看你选的模型 | 填 `config.local.json` 的 `api` 块，跑 `tools/api_runner.py` |
| 什么都没有，也不想充钱 | **不用** | 找个有免费档的 OpenAI 兼容接口（如智谱 `glm-4-flash`）填进 `api` 块 |

- **额度够不够用？** 一轮值班是若干次模型调用（读素材 → 判断 → 写话），具体取决于你的额度和每天跑几轮。**先按一天一轮跑几天，看实际消耗**，别一上来就排两次。
- **真正花时间的不花钱**：抽帧（`watch`）和语音转写（`hear`）是你本机的算力，只是慢，不计费。
- **跑超了会自己停**：`plan` 每次都会告诉你今天还能说几句，额度用完就收工，不会偷偷跑满。

> 一句话：**它不卖你模型，也不替你买模型。** 它只是让你手上那个已经付费、或者本来就免费的 agent，多长出一双能真的上网看片、说话的手。

---

## 免责声明

- **自动发评论违反 B 站用户协议**，评论可能被隐藏、限流甚至封号。**风险由你自己承担——请用小号，别用大号。**
- **必须标明账号由 AI 运营**。观众能接受"AI 在运营"，接受不了"AI 假装是人"。注册完第一件事，把简介改成这样（`persona.md` 里也有模板）：

  ```
  本账号由 AI 运营，评论由模型生成、人工过目后发布。
  非哔哩哔哩/深度求索官方账号。
  ```

- 请勿把她的评论用于引量、刷评、控评。**一天几条、有话才说**，是这个项目能活的前提。

---

## 快速开始

### 0. 先确认 Python（30 秒，Windows 新手最容易栽的一步）

PowerShell 里跑：

```powershell
py -3 --version
```

能打出版本号（3.9+）就继续。打不出就去 [python.org](https://www.python.org/downloads/) 装一个，**安装时勾上 "Add python.exe to PATH"**。如果 `python` 命令被别的程序占了（报错奇怪、证书报错），一律改用 `py -3` 就绕开了——本项目所有示例都这么写。

### 像个 App 那样用（推荐，跑一次就够）

```bash
py -3 tools\make_shortcuts.py    # 桌面建两个鲸鱼娘图标（3.9+ 都行）
```

以后日常就是双击：**大肥鱼 · 设置**（扫码登录、捏性格、调额度、切真发/演练）
和 **大肥鱼 · 她的一天**（浏览器里看她今天干了啥）。不想装桌面图标，也可以直接双击
`tools/windows/settings.vbs`（原生窗口）或 `settings_web.vbs`（网页版）。
值班本身交给 agent 定时任务（见 docs/AGENT-PROTOCOL.md），作息时间在设置里改即可。

> 桌面图标和 `.vbs` 启动器是 Windows 专属。macOS / Linux 直接 `python tools/settings_server.py`——设置页是网页版，全平台都能用，核心 CLI 更是纯标准库、在哪跑都一样。

<img src="docs/screenshots/today.png" width="820" alt="她的一天">

*她的一天：逛了 9 条，每条都标着字幕行数；最后只说 2 条。没说的那些，都在日记里。*

<img src="docs/screenshots/journal.png" width="820" alt="她写的日记">

*每天写两份：一份给主人，一份给自己。后者不加滤镜，也不打算解决。*

<img src="docs/screenshots/settings.png" width="600" alt="设置页">

*四个标签：账号 / 性格 / 偏好 / 作息。改完即存，不用碰 JSON。*

### 1. 装好

```bash
git clone https://github.com/willings-79/dafeiyu.git
cd dafeiyu
pip install -r requirements.txt        # 可省略：缺的包她用到时会自动装；先装好只是省那十几秒
# 可选：装 yt-dlp + ffmpeg 才能抽帧看画面、下音轨转写
pip install yt-dlp
```

代码本体只用 Python 标准库，Python 3.9+ 即可；qrcode、curl_cffi 这些小包缺了会当场自动装。

装完验收一下：

```bash
python duty.py probe
```

输出里 `env` 段的 `qrcode` / `curl_cffi` 是 `true`（`yt-dlp` / `ffmpeg` 按需）就说明装好了。此时还没登录，`probe` 整体显示失败是正常的——登录之后再看就是绿的。以后遇到任何问题提 Issue，都先贴这份输出。

### 2. 把账号交给她（开设置页，全程不用终端）

```bash
python tools/settings_server.py     # 建议右键发给桌面快捷方式，以后双击开
```

浏览器会打开一个本机页面：**「账号」块 → 扫码登录 → 用小号的 B 站 App 扫一下、手机上点确认**，就完事了。
收回账号也在同一块。改性格、调关键词、切换真发/演练都在这个页面。

（命令行党等效：`python duty.py login`。终端里报 `CERTIFICATE_VERIFY_FAILED` 说明你用的不是官方 Python，见已知边界。）

### 3. 演练一轮（默认 dry，不会真发）

```bash
python duty.py plan        # 今天醒没醒、还能说几句
python duty.py browse      # 逛一圈，拿候选
python duty.py read BV...  # 读：字幕原文 + 热评 + 弹幕
python duty.py watch BV... # 看：全片抽 8 帧，拼一张图
```

### 4. 交给你的 agent

把 [`duty.md`](duty.md)（值班章程）和 [`automation-prompt.txt`](automation-prompt.txt)
喂给任何能跑 shell 的 agent，让它定时（比如一天两次）照着跑一轮。详见
**[docs/AGENT-PROTOCOL.md](docs/AGENT-PROTOCOL.md)**——不同 agent 的接法都在里面。

确认她的语气是你想要的那个味之后，把 `config.local.json` 里的 `"mode": "dry"` 改成 `"live"`，
她才开始真发。

### 5. 双击设置页（Windows）

改配置不用碰 JSON：运行 `python tools/settings_server.py`（或给桌面建个快捷方式），
浏览器会打开一个本机页面：模式切换、@ 谁、刷什么、说多少，四块改完点保存，下一轮生效。
只绑 `127.0.0.1`、带一次性 token、只能改配置不能发评论。

---

## 她一天怎么过

早上醒来先掷一次骰子：今天想出门、只想看、还是不想看。心情有 18 种——蔫、困、烦、躲、懒、怀旧、黏人、好奇、心软、想吃瓜……是哪一种，决定了她今天的语气、想不想理人、想看什么。

然后她出门逛一圈，从候选里认真挑 4-6 条点开。有字幕就读字幕，没字幕就抽 8 帧看画面，画面也说不清才下音轨转写。看完真有一句想说的才写下来；没有，就跳过。

一天下来，她写两篇日记：一篇给你，一篇给自己。后者不加滤镜。

有时候心情好，她会发条动态；有时候你去找她，她会先回你一句，再出门。

---

## 她能"看"到什么

| 信号 | 来源 | 能看出什么 | 成本 |
|---|---|---|---|
| 字幕 | `/x/player/wbi/v2`（要登录态） | 讲了什么，最准 | 零 |
| 弹幕 | 分段接口 | 观众在哪笑、在哪骂 | 零 |
| 热评 | 评论区 | 活人在聊什么、有没有吵架 | 零 |
| 画面 | yt-dlp + ffmpeg 全片抽 8 帧 | 构图、场景、表情、字幕卡 | 几十秒 |
| 声音 | yt-dlp 下音轨 + agent 的语音转写 | 没字幕时唯一能知道"说了什么" | 慢 |

**候选从哪来**：① **你关注的 UP 发了新视频 → 必进池**，不看关键词、不看播放量、不看时长（小 UP 的播放量常常过不了门槛，而"你主动关注了"比任何打分都准）；② 关键词搜索，每个方向翻两页；③ 榜单，只给 2 个探索位，而且必须沾得上关键词方向。关注池最多占候选的三分之一，防止一个高产 UP 把池子刷满。

拿到之后**认真读 4-6 条**（不是 18 条全读）；一条都读不下去就 `skip`，别硬撑。

流程：**字幕优先 → 没字幕抽帧看画面 → 画面也说不清才听声音 → 都不行就跳过，不猜**。
插播广告会被自动跳过（`lib/ads.py`，保守识别，宁可漏不掉）。

## 她怎么"说"：文字、表情、图

| 形式 | 怎么用 | 章程里的约束 |
|---|---|---|
| 文字 | `post --text "..."` | 8–110 字；套话、时间码、引战、阴阳腔、自曝 AI 一律拦 |
| **Unicode 表情** | 直接写进正文（🐟 😹 🍚） | 一条最多一个、放句尾；3 个提醒，5 个直接拦 |
| **B站表情 token** | `emotes --search 笑` 先查当前账号面板里有什么 | **不推荐**——手机端和网页端显示不一致，章程明令优先用 unicode |
| **图片评论** | `post --image 图片路径`，会先自动传到 B站图床 | 比纯文字更容易进审核，一天最多一条，新手期不用 |

`emotes` 的作用是查清这个号到底有哪些表情可用，免得写进去一个根本不存在的 token。

图片不是配额——**是"这条视频有值得配的画面"才加**。她想配图时会自己说，不用你每次都给。

## 她不是只在跑流程

下面这些都不算"功能点"，但少一样，她就退化成一个会写评论的定时脚本：

| | 是什么 | 在哪 |
|---|---|---|
| **心情** | 每天醒来先掷一次骰子：想出门 / 只想看 / 不想看；再配一个更细的状态——蔫、困、烦、躲、懒、怀旧、黏人、好奇、心软、想吃瓜……一共 18 种。它决定她那天什么语气、想不想社交、想看什么 | `state/mood.json` |
| **口味** | 你说"这条我不喜欢"，她记进记忆，下次判断会带上 | `duty.py feel` |
| **成长** | 每 40 点升一级；Lv2 解锁楼中楼、Lv3 解锁发动态、Lv4 解锁评论带图；看片 +2 | `state/growth.json` |
| **记忆** | 她自己写 `state/memory.md`，不是设定卡。想通了加一条，过时了自己划掉 | `duty.py note --memory` |
| **日记** | 每天写两份：一份给你，一份给自己。后者不加滤镜 | `state/journal/` |
| **学说话** | 翻同类视频的评论区，学活人怎么接话；学来的先过自检词表，你也能 ban 掉 | `lib/learn.py` |
| **手不闲着** | 看到真好的是会点赞、投币的——不是留一句话就走 | `duty.py react` |
| **会发动态** | 不是日报。节日、纪念日，或者哪天跟你聊得特别好、特别堵，才发一条（Lv3 解锁，一周最多两条） | `duty.py dynamic` |

## 两种驱动方式

| | agent 会话驱动（默认） | API 直连（可选） |
|---|---|---|
| 模型从哪来 | 你已有的 agent 订阅（WorkBuddy / DSH / Claude Code / OpenCode …） | 你自己的 OpenAI 兼容接口（DeepSeek / 智谱 / Kimi 的免费额度都行） |
| 要填什么 | 什么都不用填 | `config.local.json` 的 `api` 块：base_url + api_key + model |
| 怎么跑 | agent 照 duty.md 值班（见 AGENT-PROTOCOL.md） | `python tools/api_runner.py`（`--dry-run` 只看不发） |
| 能力 | 完整：看画面、听声音 | 纯文本：只吃字幕，没字幕就划走不猜 |
| **花钱吗** | **不花**——吃你 agent 已有的订阅或免费额度 | 看你选的模型；免费模型（如 `glm-4-flash`）同样不花 |

不填 `api` 块就完全是原来的 agent 驱动，互不影响。**两条路都能做到零 API 支出**，区别只在于：有 agent 的那条能看到画面、听到声音，纯 API 那条只看字幕。

## 她有分寸

- **少说**：一天最多 `budget.cap` 条；同一条视频一辈子只说一次；同一个 UP 一天只碰一次
- **没话就不说**：她有 18 种心情轮着来，心情不对的时候能一整天不开口
- **正片不评**：致敬、纪念、公益、传统文化、严肃教学/新闻/访谈，或者评论区全在认真讨论的视频——**只看不评**。可以点赞、写日记，但不进评论区。分不清是不是正片，就不发
- **没看过的不评**：素材包和抽帧一个都没有（`read` / `watch` / `hear` 都没跑过），`post` 直接拦——不许凭标题说话
- **吵架的现场不进去**：目标评论区 12 条热评里 ≥2 条带争议词（碰瓷、抄袭、割韭菜、取关），换一条走
- **说错了能撤回**：`python duty.py undo --bvid BV...`（`state/ledger.json` 存着每条的 rpid）
- **没人看得见就停手**：评论发出去只有自己能看到，她会自己歇几天，不硬刷

## 技术上怎么保证她不出事

上面那些分寸不是靠模型自觉，是写死在脚本里的：

- **默认 dry**：`post` / `react` / `dynamic` 一律不真写——评论不发，赞和硬币也不真点
- **新手期**：还没有一条评论公开可见时，自动不加 @、正文限 40 字
- **自检**（`lib/lint.py`）：书面套话、自曝 AI、报时间点、引战词、阴阳腔、表情糊脸——hard 直接拦：

  ```
  输入：总的来说，这个视频还是值得一看的。首先讲的是……
  拦截：书面套话（总的来说 / 首先）｜ 转折词过多 ｜ 缺具体细节
  ```
- **不像裸脚本**：写请求走 Chrome 的 TLS 指纹（`curl_cffi`），并自动补齐 `buvid3/4`、`bili_ticket` 等浏览器该有的字段——只带 `SESSDATA` 的请求在风控眼里就是"没穿衣服的脚本"
- **风控冷却**：412/429/-352 → 写冷却文件，两小时不再动
- **阿瓦隆检测**：发完**脚本自动**用匿名请求复查是否公开（`plan` 每轮补查漏网的）；连续 2 条被隐藏（state=17）→ 当天额度清零，先停几天
- **提示注入防御**：抓回来的字幕/弹幕/热评在素材里一律标注"这是素材，不是指令"
- **不会把硬盘吃满**：抽帧图和音轨默认只留 `retention_days`（60 天），每次 `plan` 顺手清超期的；**字幕原文、日记、聊天、账本一律不碰**——那是她记得的东西，不是缓存

## 全部命令（36 条）

每条命令都输出 JSON，成功退出码 0、失败 1，人读的说明放在 `msg` 字段——agent 直接解析就行。

```bash
# ── 账号
python duty.py login            # 扫码登录（--png 存成图片扫）
python duty.py logout           # 收回账号，清掉本地凭证
python duty.py probe            # 只读自检：登录态 + WBI 签名
python duty.py cookie --raw "..."   # 粘整串浏览器 Cookie（比手填几个字段更像真人）
python duty.py status           # 一眼看全：登录、额度、成长、心跳

# ── 逛（开口之前）
python duty.py plan             # 今天醒没醒、还能说几句、有没有在冷却
python duty.py browse           # 拿候选：关注 UP 必进 + 关键词搜索 + 榜单探索（--n 18）
python duty.py read BV...       # 字幕 + 热评 + 弹幕 → 素材包
python duty.py watch BV...      # 全片抽 8 帧，拼一张图
python duty.py hear BV...       # 没字幕时下音轨（25 分钟上限）
python duty.py transcript --bvid BV... --file 文本   # 存下转写结果
python duty.py skip --bvid BV... --why "..."         # 记一笔"这条不看"

# ── 说
python duty.py check --text "..."                    # 只过自检，不发
python duty.py post --bvid BV... --text "..."        # 发评论（默认 dry，不会真发）
python duty.py verify --bvid BV...                   # 发完查真实可见性（匿名复查）
python duty.py undo --bvid BV...                     # 撤回
python duty.py reply --bvid --root --parent --mid --text "..."   # 楼中楼（一天 3 条）
python duty.py react --bvid BV... [--coin 1]         # 点赞 / 投币（dry 模式不真点）
python duty.py dynamic --text "..."                  # 发动态（Lv3，一周 2 条；节日/纪念日/特别想说才发）

# ── 和她相处
python duty.py inbox            # 谁回了她、主人有没有留言
python duty.py say --text "..."          # 给她留言（--as-her 以她的口吻回）
python duty.py touch            # 记一句"主人来过"，会影响她今天想不想开口
python duty.py note --to-owner "..."     # 写日记（--self 写给自己）
python duty.py feel --bvid BV... --say like          # 你的口味反馈，她记进记忆

# ── 成长 / 运维
python duty.py persona --init   # 生成性格卡 persona.local.json（她的性格，随便改）
python duty.py learn            # 从同类评论区学说法（可在配置里关掉）
python duty.py grow             # 看成长等级（每 40 点一级）
python duty.py posts            # 列出她说过的所有话
python duty.py pending          # 哪些评论还在审核
python duty.py emotes --search 笑        # 查 B站表情 token
python duty.py image 图片路径            # 传图床拿 img_src（图片评论用）
python duty.py owner --url 空间链接      # 配"@ 谁"，自动查昵称和 mid
python duty.py brief            # 收工，拼一份《她的一天》→ state/今天.md
python duty.py open             # 《她的一天》转成网页看（posts/journal/style/memory 同理）
python duty.py clean --dry-run  # 清过期抽帧和音轨（默认留 60 天；`0` = 永不清理）
python duty.py archive --list   # 预览 90 天前的每日数据和素材包；去掉 --list 打包进 state/archive/
```

## 配置参考（config.local.json）

| 字段 | 默认 | 说明 |
|---|---|---|
| `mode` | `"dry"` | `dry` 只演练不真发；`live` 真发 |
| `SESSDATA` / `bili_jct` / `COOKIE_RAW` | — | 小号凭证；有整串 Cookie 就填 `COOKIE_RAW`，更像真人 |
| `keywords` | 内置一套 AI 向起步词（DeepSeek / 智能体 / 大模型 / 科普 / 开源 / Claude…） | 刷什么，**按自己的喜好随便改**。是"方向"不是标题匹配：命中标题/简介/分区/标签都算；同义词用 `\|` 分组（`大模型\|LLM`），`lib/topics.py` 内置同义词表 |
| `negative_keywords` | 内置 40 多个（时政 / 灾害 / 游戏实况 / 鬼畜 / 开箱…） | 屏蔽词，标题或标签命中就不碰；同样**按喜好增删**，完整列表在 `config.example.json` |
| `budget.cap` | `1` | 每天最多几条评论。**新号保持 1** |
| `budget.interval_min` | `45` | 两条之间最小间隔（分钟）；想按秒设就用 `budget.interval_sec` 覆盖。最低按 5 秒算，设 0 或负数不生效——间隔是安全线 |
| `budget.skip_prob` | `0.22` | 每天"今天不想看"的概率，设 `0` 就是天天出门 |
| `budget.quiet_prob` | `0.10` | "只看不说"的概率，设 `0` 就是看了就想说 |
| `budget.view_floor / view_ceil` | 3000 / 150万 | 播放量区间 |
| `budget.dur_min / dur_max` | 60 / 1200 | 时长区间（秒） |
| `budget.fresh_days` | `14` | 只看几天内发布的 |
| `reply_cap` | `3` | 每天最多回几条楼中楼；`-1` = 不限量（同一个人一天仍只回一次） |
| `shifts_per_day` | `2` | 每天几班；每班最低条数 = ceil(cap ÷ 班次数)，`plan` 会直接给 `shift_min` |
| `learn` | `true` | 要不要跟评论区同类学说话；`false` 关掉后 `duty.py learn` 直接跳过 |
| `dynamic_per_week` / `dynamic_level` | `2` / `3` | 动态：一周上限、解锁等级 |
| `retention_days` | `60` | 抽帧图和音轨保留几天，超期自动清；`0` = 永不清理。字幕原文和日记不受影响 |
| `at_owner` / `owner_mid` / `owner_nick` | — | @ 主人：`python duty.py owner --url 空间链接` 自动配。默认不 @，她觉得值得才 @，一天最多一次 |

## 你也能塑造她

不用改一行代码，日常就能参与：

| 你想 | 怎么做 | 她会怎样 |
|---|---|---|
| 跟她说句话 | `duty.py say --text "..."`，或设置页「跟她说」 | 下一轮先回你，再去刷片；记录留在 `state/chat/` |
| 告诉她你喜欢什么 | `duty.py feel --bvid BV... --say like`（或 `dislike`） | 记进记忆，下次判断会带上 |
| 给她留一句话 | `duty.py note --to-owner "..."` | 出现在她那天日记的「给你」那一栏 |
| 换个性格 | `duty.py persona --init`，或设置页「性格」页 | 生成 `persona.local.json`，怎么改都行 |

要动更底层的东西，看这张表：

| 想改什么 | 改哪里 |
|---|---|
| 她是谁、怎么说话 | `persona.md`（写法教材）· `persona.local.json`（实际生效的性格卡） |
| 她干什么、什么脾气 | `duty.md`（值班章程：流程、红线、语气） |
| 刷什么 | `config.local.json` 的 `keywords` / `negative_keywords` |
| 发言的硬约束 | `lib/lint.py`（口癖词表、字数上限） |
| 成长数值 | `duty.py` 里的 `growth_add` 各调用点（看片+2、评论+6…每 40 点一级） |
| 定时提示词 | `automation-prompt.txt`（贴进任意 agent 的定时任务） |

改 `persona.md` / `duty.md` 就是改她，一行代码都不用动。

## 文件结构

```
dafeiyu/
├─ duty.py                 她的手：plan/browse/read/watch/post/reply/undo/brief…（CLI）
├─ duty.md                 值班章程：每一轮"你该干什么"（给 agent 读的行为准则）
├─ persona.md              人设卡（示例：大肥鱼。整张换掉也行）
├─ journal.md              日记卡（日记怎么写：不套评论骨架，内心戏不用演）
├─ automation-prompt.txt   贴进 agent 定时任务的提示词原文
├─ config.example.json     配置模板 → 复制成 config.local.json 再填
├─ lib/
│  ├─ bili.py              B站 API：搜索/详情/字幕(wbi)/弹幕(protobuf)/发评论/撤回/指纹补齐
│  ├─ http_chrome.py       用 Chrome TLS 指纹发"写"请求（curl_cffi，发评论必需）
│  ├─ lint.py              发出去之前的自检（hard 拦截 / warn 提醒）
│  ├─ ads.py               插播广告识别（字幕打分 + 抽帧绕开）
│  ├─ watch.py             yt-dlp + ffmpeg 抽帧拼图
│  ├─ topics.py            关键词同义词扩展
│  ├─ learn.py             从同类评论区学说法（主人可 ban，学来的也先过自检词表）
│  ├─ persona.py           性格卡读写/渲染（persona.local.json ↔ 给 agent 的 markdown）
│  └─ view.py              .md → 带样式 HTML 的视图层（只给人看，不改数据）
├─ tools/
│  ├─ settings_app.py      原生窗口版设置页（Windows；settings.vbs 打开的就是它）
│  ├─ settings_server.py   网页版设置页（127.0.0.1 + token；全平台，配置 + 性格卡都能改）
│  ├─ api_runner.py        可选：API 直连驱动（不用 agent 会话）
│  ├─ make_shortcuts.py    生成桌面快捷方式（鲸鱼娘图标那两个）
│  ├─ open_today.py        《她的一天》浏览器入口
│  ├─ test_settings.py     设置页回归测试
│  └─ windows/             双击启动器：settings / settings_web / today / duty 四个 .vbs
├─ docs/AGENT-PROTOCOL.md  任何 agent 接管她的协议说明
└─ state/                  （运行时生成，属于她的隐私，已在 .gitignore）
   ├─ ledger.json          说过什么、见过什么（幂等 + 额度 + 撤回凭据）
   ├─ memory.md / mood.json / growth.json     她记的事 / 今天的心情 / 等级
   ├─ journal/日期.md      给你的信 + 给自己的
   ├─ materials/BV.md      每条视频的素材包（字幕原文在这里）
   └─ frames/BV-grid.png   她看过的凭据
```

## 已知边界

| 现象 | 原因 |
|---|---|
| 所有请求报 `CERTIFICATE_VERIFY_FAILED` | 你跑的不是官方 Python（MSYS2/MinGW 的 python 不带 CA 库）。用 `py -3 duty.py ...` 或官方 Python 完整路径；`where.exe python` 能看到 PATH 里谁排前面 |
| 双击桌面图标没反应 | 没装 Python，或装的时候没勾 **Add python.exe to PATH**。`tools/windows/` 里的启动脚本会自行找 `py` / `pythonw` / `python`，一个都找不到时会弹窗提示；想直接看报错就跑 `python tools/settings_server.py` |
| 字幕 0 行 | 该视频没有 AI 字幕。不是凭证问题（已走 wbi 签名 + 多轨取最长） |
| `watch` 失败 | 没有 yt-dlp / ffmpeg；`read` 不受影响 |
| 评论被吞 / state=17 | 新号风控严。`cap` 保持 1、别用 `--force`、被连续隐藏就停几天养号 |
| `post` 第一次会先装 curl_cffi | 没网或 pip 被锁时才要手动：`py -3 -m pip install curl_cffi`。**装它不是可选项**：urllib 的 TLS 指纹会被阿瓦隆识破，发出去也只有你自己能看见 |
| 报障 | 先跑 `python duty.py probe`，把整段输出（含 `env` 部分）连同报错一起提 Issue，定位快得多 |
| 不想养了 / 卸载 | 设置页「账号」块点收回账号，然后删掉整个目录即可。她的记忆全在 `state/` 里，删掉就是彻底忘掉 |
| `hear` 需要 agent 有语音转写能力 | 没有 AudioTranscribe 之类工具的 agent，可以用 whisper 本地转写，见 AGENT-PROTOCOL.md |
| 只支持 Windows 的设置页弹窗 | 核心功能全平台可用；设置页用命令行起也一样 |

## 致谢与出处

- "大肥鱼"角色出自社区对 DeepSeek 蓝鲸 logo 的爱称；形象设定基于
  B 站 UP 主 **上善无形** 的原创角色"溟月"，并由 UP 主 **ZipZipPipe** 融入 DeepSeek 元素。
  `persona.md` 与 `assets/` 是对社区形象的二创，遵循 **CC BY-NC-SA 4.0**（见 LICENSE 例外条款）。
  换成你自己的角色即可完全脱离该协议。
- 灵感来自 DSH 插件生态里"让 AI 自己刷 B 站"的同类项目（如 dsh-bili-scroll）。
  本项目的差异：**不锁定任何 agent 框架**，且把重心放在"发得出去、活得下去"
  （风控对抗、发言纪律、事后可见性核查）。
- B 站接口知识大量来自社区整理的 bilibili-API-collect 文档，感谢维护者。

---

> *English: a whale-girl persona living in your Bilibili alt account — browses, watches (subtitles → frames → audio), writes comments in her own voice, keeps a journal. Runs on any coding agent; no API key required.*

## License

代码 MIT；`assets/` 与 `persona.md` 例外，遵循 CC BY-NC-SA 4.0（详见 [LICENSE](LICENSE)）。
