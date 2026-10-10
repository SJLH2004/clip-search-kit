# 贡献指南

欢迎提 Issue 和 PR。本项目刻意保持「零云依赖 + 优雅降级」，改动请遵循同样原则。

## 开发环境

```bash
git clone <repo>
cd clip-search-kit

python -m clipkit demo my-demo    # 造合成数据，不需要素材和模型
python selftest.py                # 改完必跑
```

## 提交前必须做的两件事

1. **零依赖自测必须过**：`python selftest.py` 不能引入 numpy / pillow 之外的依赖。
   新用户第一体验就是「clone 下来直接跑」，这条不能破。

2. **确认没有硬编码路径**：`clipkit` 的设计前提是「所有路径来自 clipkit.json」。
   提交前在 `clipkit/` 目录里搜一下自己的用户名、家目录、盘符路径。

## 设计约定

| 约定 | 原因 |
|---|---|
| HTTP 服务只用标准库 `http.server` | 不引入 Flask / FastAPI，降低安装门槛 |
| 重依赖一律可选 | 缺 torch / faster-whisper / tkinter 必须能降级运行，不能崩 |
| 报错要给出可执行的下一步 | 例如缺 ffmpeg 时按平台给安装命令 |
| 不谎报能力 | `doctor` 必须如实报告能不能做，不能「看起来能跑」 |
| 排序必须可解释 | 每条结果要给出命中理由，不能只有分数 |

## 改界面（模板同步）

界面资源有两份**等价副本**：

| 位置 | 用途 |
|---|---|
| `templates/` | 源码 / 技能目录形态，方便直接编辑 |
| `clipkit/templates/` | 打包进 wheel，pip 安装后从这儿读 |

**改完必须同步两份**，否则源码跑出来的界面和 pip 装出来的不一样：

```bash
cp templates/*.js templates/*.css templates/*.html clipkit/templates/
python selftest.py     # 会逐字节比对，漂移直接报错
```

自检里的「模板两份副本一致」就是专门防这个的。

## 加新命令

1. 在 `clipkit/commands.py` 里实现 `cmd_<name>(args)`
2. 在 `clipkit/__main__.py` 的 `build_parser()` 里注册子命令
3. 在 `selftest.py` 里加对应检查
4. 更新 `README.md` 和 `CHANGELOG.md`

## 报告问题

请附上 `python -m clipkit doctor` 的完整输出 —— 它包含定位问题所需的全部环境信息。