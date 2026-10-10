# -*- coding: utf-8 -*-
"""clipkit 图形面板（tkinter）。由 启动器.py 调用。"""
import os, socket, subprocess, sys, threading, time, webbrowser

import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = HERE   # clipkit 包就在技能根目录下
if SKILL not in sys.path:
    sys.path.insert(0, SKILL)


def _port_free(port):
    s = socket.socket()
    try:
        s.bind(("127.0.0.1", int(port)))
        return True
    except OSError:
        return False
    finally:
        s.close()


class Panel(object):
    def __init__(self, root):
        from clipkit import config as C
        self.C = C
        self.cfg = C.load(required=False)
        self.root = root
        root.title("clipkit · 素材语义检索")
        root.geometry("960x660")
        root.minsize(780, 540)

        top = tk.Frame(root, padx=12, pady=10)
        top.pack(fill="x")
        tk.Label(top, text="项目目录").grid(row=0, column=0, sticky="w")
        self.dir_var = tk.StringVar(value=self.cfg.root if self.cfg else os.getcwd())
        tk.Entry(top, textvariable=self.dir_var, width=64).grid(row=0, column=1, padx=6, sticky="we")
        tk.Button(top, text="选择…", command=self.pick_dir).grid(row=0, column=2)
        tk.Label(top, text="端口").grid(row=1, column=0, sticky="w", pady=(6, 0))
        self.port_var = tk.StringVar(value=str((self.cfg.data.get("port") if self.cfg else 0) or 8777))
        tk.Entry(top, textvariable=self.port_var, width=8).grid(row=1, column=1, sticky="w", padx=6, pady=(6, 0))
        top.columnconfigure(1, weight=1)

        bar = tk.Frame(root, padx=12)
        bar.pack(fill="x")
        self.buttons = []
        for text, args in (
            ("① 体检", ["doctor"]),
            ("② 初始化", ["__INIT__"]),
            ("③ 扫描", ["scan"]),
            ("④ 抽帧", ["frames"]),
            ("⑤ 建索引", ["index"]),
            ("⑥ 启动服务", ["__SERVE__"]),
            ("查询", ["__QUERY__"]),
            ("演示数据", ["demo", "clipkit-demo"]),
        ):
            b = tk.Button(bar, text=text, width=11, command=lambda a=args: self.click(a))
            b.pack(side="left", padx=3)
            self.buttons.append(b)
        tk.Button(bar, text="停止", width=7, fg="#a33", command=self.stop).pack(side="left", padx=10)

        import platform
        mono = ("Consolas" if platform.system() == "Windows"
                else ("Menlo" if platform.system() == "Darwin" else "DejaVu Sans Mono"))
        self.out = tk.Text(root, wrap="none", bg="#111", fg="#ddd",
                           insertbackground="#ddd", font=(mono, 9))
        self.out.pack(fill="both", expand=True, padx=12, pady=10)
        sb = tk.Scrollbar(self.out)
        sb.pack(side="right", fill="y")
        self.out.config(yscrollcommand=sb.set)
        sb.config(command=self.out.yview)

        self.proc = None
        self.busy = False
        self.log("clipkit 面板就绪。" + chr(10))
        self.log("建议顺序：① 体检 → ② 初始化 → ③ 扫描 → ④ 抽帧 → ⑤ 建索引 → ⑥ 启动服务" + chr(10))
        self.log("想先看效果：点「演示数据」，再点 ⑥。" + chr(10) + chr(10))

    def log(self, s):
        self.out.insert("end", s)
        self.out.see("end")

    def pick_dir(self):
        d = filedialog.askdirectory(initialdir=self.dir_var.get())
        if d:
            self.dir_var.set(d)

    def _run(self, args, cwd, on_done=None):
        if self.busy:
            self.log("[忙] 上一条命令还在跑。" + chr(10))
            return
        self.busy = True
        env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8", PYTHONPATH=SKILL)
        self.log(chr(10) + "$ clipkit " + " ".join(args) + chr(10))

        def worker():
            try:
                self.proc = subprocess.Popen(
                    [sys.executable, "-u", "-m", "clipkit"] + list(args), cwd=cwd, env=env,
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                for line in self.proc.stdout:
                    self.root.after(0, self.log, line.decode("utf-8", "replace"))
                self.proc.wait()
                self.proc = None
            except Exception as e:
                self.root.after(0, self.log, "[错误] %s: %s" % (type(e).__name__, e))
            finally:
                self.busy = False
                if on_done:
                    self.root.after(0, on_done)

        threading.Thread(target=worker, daemon=True).start()

    def click(self, args):
        cwd = self.dir_var.get()
        if not os.path.isdir(cwd):
            messagebox.showerror("目录不存在", cwd)
            return
        if args == ["__INIT__"]:
            d = filedialog.askdirectory(title="选择包含视频素材的目录")
            if d:
                self._run(["init", "--media", d, "--project", cwd], cwd)
            return
        if args == ["__QUERY__"]:
            q = simpledialog.askstring("查询", "输入中文描述（例如：抱拳行礼）")
            if q:
                self._run(["query", q], cwd)
            return
        if args == ["__SERVE__"]:
            port = self.port_var.get()
            if not _port_free(port):
                if not messagebox.askyesno("端口被占", "端口 %s 已被占用。直接打开已有服务吗？" % port):
                    return
                webbrowser.open("http://127.0.0.1:%s" % port)
                return
            webbrowser.open("http://127.0.0.1:%s" % port)
            self._run(["serve", "--port", port], cwd)
            return
        self._run(args, cwd)

    def stop(self):
        if self.proc:
            try:
                self.proc.terminate()
                self.log("[已停止]" + chr(10))
            except Exception:
                pass