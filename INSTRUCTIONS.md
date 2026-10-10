# clipkit · 给任意智能体的接入说明

这份文件是给「不认识 SKILL.md 规范」的智能体/工具链看的。
只要你的 agent 能**读文件**并且**执行 shell 命令**，就能用这套能力，不需要任何 SDK 或插件。

## 它能做什么

输入一句中文，找到视频素材里对应的画面帧或台词，并给出：素材名、在素材里的时间点、命中理由。

## 先装一次（只做一次）

```bash
pip install --user --no-deps /path/to/clip-search-kit
```

装完后 `python -m clipkit` 在**任何目录**都能用。不想装就设 `PYTHONPATH=<技能目录>`。

## 怎么调用（三件事）

1. **先确认环境**

   ```bash
   python -m clipkit doctor
   ```

   输出会明确说明：现在能做到什么、不能做到什么、缺什么怎么补。
   这一步是幂等只读的，可以随便跑。

2. **初始化项目**（如果 `clipkit.json` 还不存在）

   ```bash
   python -m clipkit init --media "/path/to/footage"
   ```

3. **用起来**

   ```bash
   python -m clipkit query "抱拳行礼"          # 画面检索
   python -m clipkit query "师父" --subs       # 台词检索
   python -m clipkit query "抱拳" --json       # 机器可读输出（给 agent 解析）
   python -m clipkit serve                     # 起网页界面
   ```

## 建议的调用顺序（首次使用某个素材目录）

```
doctor  →  init  →  scan  →  frames  →  index  →  tag  →  transcribe  →  serve
```

- 每步都可重复跑：已有产物默认跳过。
- **重依赖缺失不是错误**：没有 torch 会退化成关键词检索；没有 faster-whisper 就没有台词检索。
  不要因为 `doctor` 报某个模块缺失就认为技能不可用 —— 先看它「能做什么」那一段。
- 想零依赖验证：`python -m clipkit demo /tmp/demo && cd /tmp/demo && python -m clipkit serve`

## 给 agent 的行为约定（重要）

1. **不要编造中文描述**去凑 `tag` 步骤 —— 那一步需要视觉模型 API Key，没有就跳过。
2. **不要声称检索结果是精确匹配**。每条素材只抽 3 帧，时间码是粗定位（约 20%/50%/80%）。
3. **不要把排序当结论**。这是模糊排序，必须提示用户人工核对。
4. 用户问「有没有这个镜头」时，报告**素材名 + 时间点 + 命中理由**，而不是只说「有」。

## 输出格式（`--json`）

```json
{
  "meta": {"mode": "hybrid|keyword", "terms": ["抱拳", "行礼"]},
  "results": [
    {"rank": 1, "clip": "DSC_6267", "frame": "f1", "approx_sec": "4.7s",
     "score": 0.5173, "sim": 0.4173, "hits": ["抱拳"],
     "desc": "主体: ...
动作: ...", "keywords": ["武术", "抱拳"], "cats": ["手部特写"]}
  ]
}
```

## 平台差异

- **Windows**：`启动.bat` 可用；控制台默认 GBK，入口已做 UTF-8 兜底。
- **macOS / Linux**：用 `./start.sh`；ffmpeg 需 `brew install ffmpeg` 或 `apt install ffmpeg`。
- `clipkit` 只用标准库 + numpy，**没有平台专属路径**。