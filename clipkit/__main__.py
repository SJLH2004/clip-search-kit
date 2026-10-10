# -*- coding: utf-8 -*-
"""命令行入口：python -m clipkit <命令>"""
import argparse, os, sys, json

from . import __version__, config as C


def build_parser():
    p = argparse.ArgumentParser(
        prog="clipkit",
        description="素材语义检索工具箱：把一目录视频变成能说人话检索的本地服务",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""常用流程：
  clipkit init --media "D:/素材"      在当前目录建配置
  clipkit doctor                     体检：缺什么、怎么补
  clipkit scan                       扫描素材目录，生成清单
  clipkit frames                     按 20%/50%/80% 抽帧
  clipkit index                      建 CLIP 向量索引（需要 torch）
  clipkit tag                        用视觉大模型给每帧写中文描述（需要 API Key）
  clipkit transcribe                 本地转写台词（需要 faster-whisper）
  clipkit serve                      启动检索服务
  clipkit query "抱拳行礼"            命令行里直接查
""")
    p.add_argument("--version", action="version", version="clipkit " + __version__)
    sub = p.add_subparsers(dest="cmd")

    s = sub.add_parser("init", help="建立 clipkit.json")
    s.add_argument("--media", action="append", required=True, help="素材目录，可多次")
    s.add_argument("--project", default=None, help="项目根目录，默认当前目录")
    s.add_argument("--port", type=int, default=None)
    s.add_argument("--force", action="store_true")

    sub.add_parser("doctor", help="体检：环境、数据、缺什么")

    s = sub.add_parser("scan", help="扫描素材目录，生成 media_index.csv")
    s.add_argument("--limit", type=int, default=0, help="只扫前 N 个（调试用）")

    s = sub.add_parser("frames", help="抽帧")
    s.add_argument("--workers", type=int, default=4)
    s.add_argument("--force", action="store_true", help="重抽已有帧")

    s = sub.add_parser("index", help="建 CLIP 向量索引")
    s.add_argument("--batch", type=int, default=32)

    s = sub.add_parser("tag", help="VLM 画面描述")
    s.add_argument("--provider", default=None, choices=["zhipu", "moonshot", "ark"])
    s.add_argument("--limit", type=int, default=0)
    s.add_argument("--only", default=None, help="只处理某条素材")

    s = sub.add_parser("transcribe", help="本地语音转写")
    s.add_argument("--model", default=None, help="tiny/base/small/medium/large-v3")
    s.add_argument("--limit", type=int, default=0)

    s = sub.add_parser("serve", help="启动检索服务")
    s.add_argument("--host", default=None)
    s.add_argument("--port", type=int, default=None)
    s.add_argument("--no-semantic", action="store_true", help="只做关键词，不加载模型")

    s = sub.add_parser("query", help="命令行检索")
    s.add_argument("q", help="中文描述或台词")
    s.add_argument("--top", type=int, default=10)
    s.add_argument("--subs", action="store_true", help="搜台词而不是画面")
    s.add_argument("--no-semantic", action="store_true", help="不加载模型，只做关键词")
    s.add_argument("--json", action="store_true", help="输出 JSON")

    s = sub.add_parser("demo", help="造一份演示数据，不依赖任何素材和模型")
    s.add_argument("dir", nargs="?", default="clipkit-demo")

    s = sub.add_parser("update", help="更新 clipkit.json 里的字段")
    s.add_argument("--venv", default=None, help="指定 Python 解释器")
    s.add_argument("--python-exe", default=None, help="同 --venv")
    s.add_argument("--media", action="append", default=None)
    s.add_argument("--port", type=int, default=None)
    s.add_argument("--set", action="append", default=None, help="任意字段 key=value")

    return p


def main(argv=None):
    _console_utf8()   # 直接调用 main() 时也要兜住 Windows GBK 控制台
    args = build_parser().parse_args(argv)
    cmd = args.cmd or "doctor"
    try:
        from . import commands as CMD
    except ImportError as e:
        raise SystemExit("内部模块缺失：" + str(e))
    fn = getattr(CMD, "cmd_" + cmd.replace("-", "_"), None)
    if fn is None:
        raise SystemExit("未知命令：" + cmd)
    return fn(args) or 0

def _console_utf8():
    """Windows 控制台默认 GBK，输出中文和符号会崩；这里兜一下"""
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


if __name__ == "__main__":
    _console_utf8()
    sys.exit(main())