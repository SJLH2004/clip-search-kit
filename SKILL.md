---
name: clip-search-kit
description: >-
  把一目录视频素材变成「说人话就能找到画面和台词」的本地语义检索服务。
  当用户想按内容（而不是文件名）找素材、想给素材建可搜索索引、想做画面/台词检索、
  想快速定位某个镜头在第几条素材的什么位置时使用。
  也适用于：素材太多记不住文件名、剪辑时找不到「那个抱拳的镜头」、
  想把口述台词做成可检索字幕库、想批量给素材打中文描述标签。
description_en: >-
  Turn a folder of video footage into a local Chinese semantic search service
  ("find the shot where someone salutes"). Use when the user wants to search
  footage by content rather than filename, build a searchable index of clips,
  locate a specific shot's position across source files, or turn spoken dialogue
  into a searchable subtitle库.
version: 1.0.0
author: lead
level: personal
---

# clipkit · 素材语义检索工具箱

把一个充满视频素材的目录，变成本地可检索的「素材库」——输入中文描述就能找到画面帧，
输入台词就能定位到具体素材的秒数。**全程本地运行，不上传任何素材。**

## 什么时候用这个技能

- 用户说「找不到那个镜头」「素材太多记不住」「想按内容搜素材」
- 用户要做**素材检索/语义搜索/画面搜索/台词搜索**
- 用户有一堆素材要整理、要按内容分类、要快速定位某个镜头
- 用户想把口述/对白变成可搜索的文字库
- 用户提到 Chinese-CLIP、CLIP 检索、向量检索素材、VLM 打标

## 它解决什么问题

传统做法是按文件名找素材（`DSC_6267.MOV`），但剪辑时人记住的是**内容**
（「那个抱拳行礼的镜头」「师父讲传承那段」）。clipkit 建立「内容 → 素材 + 时间点」的映射：

| 能力 | 说明 |
|---|---|
| **画面语义检索** | 中文描述 → 最像的画面帧 + 所属素材 + 大致时间码 |
| **VLM 描述混合排序** | 视觉相似度 + 画面描述关键词加权，排序区分度更高，且给出**命中理由** |
| **台词检索** | 关键词优先，无命中时用 CLIP 做语义兜底 |
| **时间线视图** | 把命中画面和台词按时间码合并，看清「第几秒是什么画面、谁在说话」 |
| **分类筛选** | 从 VLM 的景别/器械等结构化字段推导类别 |

## 快速开始

```bash
# 1) 在当前项目里初始化（素材目录可以有多个）
python -m clipkit init --media "D:/素材目录"

# 2) 体检：告诉你缺什么、怎么补
python -m clipkit doctor

# 3) 走流水线（缺哪步补哪步，每步都能单独重跑）
python -m clipkit scan        # 扫描素材，生成清单
python -m clipkit frames      # 按 20%/50%/80% 抽帧
python -m clipkit index       # 建 CLIP 向量索引（需要 torch）
python -m clipkit tag         # VLM 写中文描述（需要 API Key）
python -m clipkit transcribe  # 本地转写台词（需要 faster-whisper）

# 4) 用起来
python -m clipkit serve       # 启动网页检索
python -m clipkit query "抱拳行礼"
```

**没有素材、没有模型也想看效果**：

```bash
python -m clipkit demo my-demo
cd my-demo && python -m clipkit serve
```

## 界面（三层自动降级）

给不想敲命令行的人：双击 `启动.bat`，或 `python 启动器.py`。

| 方式 | 条件 | 说明 |
|---|---|---|
| **图形面板** | 当前 Python 有 tkinter | 按钮式面板，①→⑥ 顺序点，启动服务自动开浏览器 |
| **控制台菜单** | 没有 tkinter（精简版/嵌入式 Python 常见） | 功能完全一样，数字选菜单 |
| **Web 面板** | 任何情况 | `python 启动器.py --web` 直接起服务并开浏览器 |

强制指定：`--gui` / `--menu` / `--web`。

> 注意：Windows 官方 **embeddable** 版 Python 不含 Tcl/Tk，所以 `tkinter` 可能缺失。
> 这不是故障，启动器会自动切到控制台菜单。

## 关键约定

- **所有路径来自 `clipkit.json`**，代码里没有任何硬编码路径。配置文件可丢进版本库。
- **每步都可重入**：已有产物默认跳过，`--force` 重做。
- **重依赖全部可选**：没有 torch 就退化为关键词检索；没有 faster-whisper 就没有台词检索。
  `doctor` 会明确告诉你当前能做到什么、不能做到什么。**不会假装能干。**
- **抽帧是粗定位**：每条素材只抽 3 帧，所以「命中 f2 帧」≈ 50% 处，不是精确帧号。
  要精确就调大 `frame_fracs`。

## 数据格式（便于与其它工具对接）

| 文件 | 内容 |
|---|---|
| `clipkit.json` | 配置：素材目录、抽帧比例、模型、端口 |
| `.clipkit/index/index.csv` | 每帧：`img, clip, frame, at, approx_sec, group, dur` |
| `.clipkit/index/vectors.npy` | 帧向量，与 index.csv 行序一一对应 |
| `.clipkit/tags/tags.jsonl` | 每帧 VLM 描述：`{clip, frame, desc, tags[], ok}` |
| `.clipkit/transcripts/transcripts.jsonl` | 每条素材台词：`{clip, dur, segments:[{start,end,text}]}` |

## 技术要点（排查问题时看）

- 检索引擎在 `clipkit/search.py`：向量可用时走混合排序，否则纯关键词降级。
- 分类规则在 `clipkit/store.py` 的 `infer_cats()`：优先用 VLM 的 `画面: 近景；有手部特写；有器械` 结构化字段。
- Web 层 `clipkit/web.py` 只用标准库 http.server；界面资源在 `templates/`，改完重启即可。
- **Windows 控制台默认 GBK**，打印中文/符号可能崩；入口已做 UTF-8 兜底。
- 端口被占时换个端口：`python -m clipkit serve --port 8899`。

## 已知边界

- 画面检索是**模糊排序**，不是精确匹配。结果必须人工核对，不要把排序当结论。
- 纯英文查询走中文 CLIP，效果一般，建议用中文。
- 词表语义兜底（`clipkit/wordvec.py`）**只对 demo 数据生效**，真实项目需要 torch 才有语义能力。