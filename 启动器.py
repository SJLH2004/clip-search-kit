# -*- coding: utf-8 -*-
"""clipkit 启动器 —— 三种界面自动降级，哪台机器都能用。

  python 启动器.py          自动挑：有 tkinter 就用图形面板，否则用控制台菜单
  python 启动器.py --gui    强制图形面板
  python 启动器.py --menu   强制控制台菜单
  python 启动器.py --web    直接启动服务并打开浏览器

图形面板依赖 tkinter。部分精简版/嵌入式 Python 不含 Tcl/Tk，这时会自动切到控制台菜单，
功能完全一样。
"""
import os, subprocess, sys, time, webbrowser

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = HERE   # clipkit 包就在技能根目录下
if SKILL not in sys.path:
    sys.path.insert(0, SKILL)


def _console_utf8():
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def has_tk():
    try:
        import tkinter  # noqa: F401
        return True
    except Exception:
        return False


def load_cfg():
    from clipkit import config as C
    return C.load(required=False)


def project_dir(cfg):
    return cfg.root if cfg else os.getcwd()


def port_of(cfg):
    return int((cfg.data.get("port") if cfg else 0) or 8777)


class Runner(object):
    """跑一条 clipkit 命令，输出直接透传到当前控制台"""

    def run(self, args, cwd, title=None):
        env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8", PYTHONPATH=SKILL)
        print("")
        print("─" * 62)
        print("$ clipkit " + " ".join(args))
        print("─" * 62)
        try:
            subprocess.call([sys.executable, "-m", "clipkit"] + list(args), cwd=cwd, env=env)
        except KeyboardInterrupt:
            print(chr(10) + "[已中断]")
        except Exception as e:
            print("[错误] %s: %s" % (type(e).__name__, e))
        print("")


MENU = [
    ("体检：看看缺什么、现在能做什么", ["doctor"]),
    ("初始化：选择素材目录，生成 clipkit.json", ["__INIT__"]),
    ("扫描素材目录，生成清单", ["scan"]),
    ("抽帧（每条素材 20%/50%/80%）", ["frames"]),
    ("建 CLIP 向量索引（需要 torch）", ["index"]),
    ("VLM 打标：给每帧写中文描述（需要 API Key）", ["tag"]),
    ("本地转写台词（需要 faster-whisper）", ["transcribe"]),
    ("启动检索服务（会打开浏览器）", ["__SERVE__"]),
    ("命令行查询一次", ["__QUERY__"]),
    ("造演示数据（不需要素材和模型）", ["demo", "clipkit-demo"]),
]


def menu(cfg):
    r = Runner()
    while True:
        cwd = project_dir(cfg)
        port = port_of(cfg)
        print("")
        print("=" * 62)
        print("  clipkit · 素材语义检索")
        print("  项目目录： " + cwd)
        print("  服务端口： " + str(port))
        print("=" * 62)
        for i, (label, _) in enumerate(MENU, 1):
            print("  %2d) %s" % (i, label))
        print("   0) 退出")
        print("")
        try:
            raw = input("请选择 [0-%d]： " % len(MENU)).strip()
        except (EOFError, KeyboardInterrupt):
            print("")
            return 0
        if raw in ("0", "q", "Q", ""):
            return 0
        if not raw.isdigit() or not (1 <= int(raw) <= len(MENU)):
            print("请输入 0 ~ %d 之间的数字。" % len(MENU));
            continue
        args = list(MENU[int(raw) - 1][1])

        if args == ["__INIT__"]:
            d = input("素材目录的完整路径（可留空跳过）： ").strip().strip(chr(34))
            if not d:
                continue
            if not os.path.isdir(d):
                print("目录不存在：" + d);
                continue
            r.run(["init", "--media", d, "--project", cwd], cwd)
            cfg = load_cfg()
            continue

        if args == ["__QUERY__"]:
            q = input("输入中文描述（例如：抱拳行礼）： ").strip()
            if not q:
                continue
            subs = input("搜台词吗？(y/N)： ").strip().lower() == "y"
            a = ["query", q] + (["--subs"] if subs else [])
            r.run(a, cwd)
            continue

        if args == ["__SERVE__"]:
            import socket
            s = socket.socket()
            try:
                s.bind(("127.0.0.1", port));
                free = True
            except OSError:
                free = False
            finally:
                s.close()
            if not free:
                print("端口 %d 已被占用。可能是服务已经在跑。" % port)
                p2 = input("换一个端口（直接回车表示打开已有服务）： ").strip()
                if p2.isdigit():
                    port = int(p2)
                else:
                    webbrowser.open("http://127.0.0.1:%d" % port)
                    continue
            print("正在启动 http://127.0.0.1:%d （按 Ctrl+C 停止）" % port)
            time.sleep(0.8)
            webbrowser.open("http://127.0.0.1:%d" % port)
            r.run(["serve", "--port", str(port)], cwd)
            continue

        r.run(args, cwd)
        cfg = load_cfg()


def run_gui():
    import tkinter as tk
    import importlib.util
    p = os.path.join(HERE, "gui.py")
    spec = importlib.util.spec_from_file_location("clipkit_gui", p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    root = tk.Tk()
    m.Panel(root)
    root.mainloop()
    return 0


def main():
    _console_utf8()
    args = sys.argv[1:]
    cfg = load_cfg()
    if "--web" in args:
        port = port_of(cfg)
        env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8", PYTHONPATH=SKILL)
        time.sleep(0.8)
        webbrowser.open("http://127.0.0.1:%d" % port)
        return subprocess.call(
            [sys.executable, "-m", "clipkit", "serve", "--port", str(port)],
            cwd=project_dir(cfg), env=env)
    if "--menu" in args:
        return menu(cfg)
    if "--gui" in args or (not args and has_tk()):
        if has_tk():
            try:
                return run_gui()
            except Exception as e:
                print("[图形面板启动失败] %s: %s" % (type(e).__name__, e))
                print("改用控制台菜单。")
        else:
            print("[提示] 这个 Python 没有 tkinter，改用控制台菜单。")
            print("       想要图形面板：换一个带 tkinter 的 Python 跑本脚本。")
    return menu(cfg)


if __name__ == "__main__":
    sys.exit(main())