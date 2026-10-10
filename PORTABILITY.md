# 在别的智能体里使用 clip-search-kit

## 一句话结论

**可以。** 这套东西的形态是「**一个规范目录 + 一个独立 CLI**」：

- `SKILL.md` —— 按通用 YAML frontmatter 规范写的技能描述
- `clipkit/` —— 纯 Python CLI，只用标准库 + numpy，**无平台专属路径、无云依赖**

所以只要目标智能体满足「**能读文件** + **能执行 shell**」，就能用。
**换了智能体，检索逻辑和界面一行都不用改。**

## 各平台的接入方式

| 平台 | 接入方式 | 是否需要改造 |
|---|---|---|
| **WorkBuddy / SkillHub** | 放到 `~/.workbuddy/skills/clip-search-kit/` | 不需要，原生格式 |
| **DSH** | 放到其 skills 目录 | 不需要，`SKILL.md` 同规范 |
| **Claude / Claude Code（Skills）** | 拷到 `~/.claude/skills/clip-search-kit/` | 不需要，`SKILL.md` 规范同源 |
| **OpenAI Codex / Cursor / Copilot** | 把 `INSTRUCTIONS.md` 并入 `AGENTS.md` 或规则文件 | 只需合并文档，CLI 原样可用 |
| **任意自研 Agent** | system prompt 里加一句「可用 python -m clipkit 做素材检索」 | 只需加提示 |
| **纯人工 / 命令行** | 直接 `python -m clipkit --help` | 不需要智能体 |

`SKILL.md` 的 frontmatter 只有 `name` / `description` 是硬要求，其余字段各平台会忽略不认识的键，
所以同一份文件可以同时被多家识别。

## 目标环境需要什么

**必需**：Python ≥ 3.9

**强烈建议**：numpy（向量检索）、pillow（抽帧）、ffmpeg（抽帧与抽音轨）

**可选（缺了会自动降级，不会报错）**：

| 依赖 | 缺了会怎样 |
|---|---|
| torch + transformers | 退化为「纯关键词」检索（用 VLM 描述文本），可用但召回弱 |
| faster-whisper | 没有台词检索，画面检索不受影响 |
| tkinter | 图形面板不可用，自动切控制台菜单 |
| VLM API Key | 跳过 tag 步骤，没有画面描述与分类筛选 |

> `doctor` 会**逐项如实报告**当前能力边界，不会假装能干活。

## 迁移到新机器 / 新智能体的步骤

```bash
# 1) 解压到目标机器的 skills 目录（按平台选一个）
cp -r clip-search-kit ~/.workbuddy/skills/
cp -r clip-search-kit ~/.claude/skills/

# 2) 装基础依赖
pip install numpy pillow
brew install ffmpeg        # 或 apt install ffmpeg

# 3) 自检（约 30 秒，用合成数据，不需要素材和模型）
python selftest.py

# 4) 建项目
python -m clipkit init --media "/path/to/footage"
python -m clipkit doctor
```

`selftest.py` 成功 = 这套东西在目标环境上确实能跑，不是「看起来能跑」。

## 需要重新做一次的事

**索引和描述跟素材绑定**：换机器时数据本身可以拷，但路径要改。

| 产物 | 能否直接拷 | 说明 |
|---|---|---|
| `clipkit.json` | 可以 | 里面的路径要改（`clipkit update` 或直接编辑） |
| `index.csv` + `vectors.npy` | 可以 | 只要帧图目录结构一致 |
| `tags.jsonl` | 可以 | 纯文本 |
| `transcripts.jsonl` | 可以 | 纯文本 |
| 素材帧/ 帧图 | 可以 | 体积大，通常在新机器上 `clipkit frames` 重抽更快 |

最省事的迁移：**只搬 `clipkit.json` + `.clipkit/` 目录，帧图在新机器重抽。**

## 已知的移植注意事项

1. **控制台编码**：Windows 默认 GBK，脚本入口已做 UTF-8 兜底；自己写包装脚本记得 `PYTHONUTF8=1`。
2. **`python -m clipkit` 要求包在 `sys.path` 上**。三种解法（推荐第一种）：

   ```bash
   # ① 装进 Python 环境（之后任何目录都能用，可逆）
   pip install --user --no-deps .

   # ② 设环境变量
   export PYTHONPATH=/path/to/clip-search-kit

   # ③ cd 到技能目录再跑（启动器 / start.sh 已自动处理）
   ```

   `pip install` 后 `clipkit --version` 也可用；但脚本目录可能不在 PATH，按 pip 的提示加一下。
3. **`启动.bat` 仅 Windows**，macOS/Linux 用 `start.sh`。
4. **端口占用**：默认 8777，被占时 `clipkit serve --port 8899`。
5. **模型下载**：首次用中文-CLIP 会从 HuggingFace 拉约 600MB；国内建议设
   `HF_ENDPOINT=https://hf-mirror.com`（代码已默认走镜像）。
