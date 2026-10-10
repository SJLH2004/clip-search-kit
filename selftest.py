# -*- coding: utf-8 -*-
"""clipkit 自测：不依赖素材和模型，用合成数据验证整条链路。"""
"""
用法： python selftest.py
覆盖：技能包结构 / CLI / 缺配置行为 / demo 造数 / doctor / query / serve+API / 重入
"""
import subprocess, sys, os, json, shutil, time, socket, urllib.request, urllib.parse

# 自测本身必须零依赖可跑：重依赖缺失时，相关断言改为「按设计跳过」
import importlib.util as _ilu
HAS_NUMPY = _ilu.find_spec("numpy") is not None
HAS_PIL = _ilu.find_spec("PIL") is not None

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
TMP = os.path.join(os.path.dirname(HERE), "_clipkit_selftest")

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def main():
    if os.path.isdir(TMP):
        shutil.rmtree(TMP, ignore_errors=True)
    os.makedirs(TMP, exist_ok=True)
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8", PYTHONPATH=HERE)
    ok = [0]
    fail = [0]

    def check(name, cond, extra=""):
        if cond:
            ok[0] += 1
            print("  PASS  %-36s %s" % (name, extra))
        else:
            fail[0] += 1
            print("  FAIL  %-36s %s" % (name, extra))

    def run(args, cwd=None, timeout=300):
        p = subprocess.run([PY, "-m", "clipkit"] + list(args), cwd=cwd or TMP, env=env,
                           timeout=timeout, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        return p.returncode, p.stdout.decode("utf-8", "replace")

    print("== 技能包结构 ==")
    for f in ("SKILL.md", "启动器.py", "启动.bat", "clipkit/__main__.py", "clipkit/web.py",
              "pyproject.toml", "manifest.json", "INSTRUCTIONS.md", "PORTABILITY.md"):
        check("存在 " + f, os.path.isfile(os.path.join(HERE, f)))
    # 界面资源：源码布局在 templates/，pip 安装布局在 clipkit/templates/
    def has_tpl(name):
        return (os.path.isfile(os.path.join(HERE, "templates", name))
                or os.path.isfile(os.path.join(HERE, "clipkit", "templates", name)))
    for name in ("app.js", "app.css", "app.html"):
        check("存在界面资源 " + name, has_tpl(name))
    # 模板漂移防护：源码布局与包内布局必须逐字节一致（否则 pip 装出来和源码跑出来不一样）
    src_dir = os.path.join(HERE, "templates")
    pkg_dir = os.path.join(HERE, "clipkit", "templates")
    if os.path.isdir(src_dir) and os.path.isdir(pkg_dir):
        import hashlib
        drift = []
        for nm in sorted(os.listdir(src_dir)):
            a = os.path.join(src_dir, nm)
            b = os.path.join(pkg_dir, nm)
            if not os.path.isfile(a):
                continue
            if not os.path.isfile(b):
                drift.append(nm + "(包内缺失)")
                continue
            ha = hashlib.sha256(open(a, "rb").read()).hexdigest()
            hb = hashlib.sha256(open(b, "rb").read()).hexdigest()
            if ha != hb:
                drift.append(nm + "(内容不一致)")
        check("模板两份副本一致", not drift, ",".join(drift) if drift else "templates/ == clipkit/templates/")
    sm = open(os.path.join(HERE, "SKILL.md"), encoding="utf-8").read()
    check("SKILL.md frontmatter", sm.startswith("---") and "name: clip-search-kit" in sm)

    print("== CLI ==")
    rc, out = run(["--help"])
    check("--help 列出全部命令", rc == 0 and all(c in out for c in
          ["init", "doctor", "scan", "frames", "index", "tag", "transcribe",
           "serve", "query", "demo", "update"]))
    rc, out = run(["doctor"])
    check("缺配置时给可操作提示", rc != 0 and "clipkit.json" in out)

    print("== demo 造数 ==")
    rc, out = run(["demo", "demo-proj"])
    check("demo 成功", rc == 0 and "造好演示数据" in out)
    D = os.path.join(TMP, "demo-proj")
    for f, label in (("clipkit.json", "配置"), (".clipkit/index/index.csv", "索引"),
                     (".clipkit/tags/tags.jsonl", "描述"),
                     (".clipkit/transcripts/transcripts.jsonl", "台词")):
        check("生成" + label, os.path.isfile(os.path.join(D, f)))
    # 向量文件：有 numpy 才生成
    vec = os.path.isfile(os.path.join(D, ".clipkit/index/vectors.npy"))
    if HAS_NUMPY:
        check("生成向量（有 numpy）", vec)
    else:
        check("生成向量（无 numpy 时按设计跳过）", not vec)
    tdir = os.path.join(D, "素材帧")
    n = len([x for x in os.listdir(tdir) if x.endswith(".jpg")]) if os.path.isdir(tdir) else 0
    if HAS_PIL:
        check("生成帧图（有 Pillow）", n >= 72, "%d 张" % n)
    else:
        check("生成帧图（无 Pillow 时按设计跳过）", n == 0, "%d 张" % n)

    print("== doctor / query ==")
    rc, out = run(["doctor"], cwd=D)
    check("doctor 报数据量", rc == 0 and "72 帧" in out and "24 条素材" in out)
    rc, out = run(["query", "抱拳行礼"], cwd=D)
    check("关键词命中画面", rc == 0 and "DEMO_0001" in out)
    rc, out = run(["query", "师父", "--subs"], cwd=D)
    check("台词检索命中", rc == 0 and "师父说" in out)
    rc, out = run(["update", "--port", "8899"], cwd=D)
    check("update 改配置", rc == 0 and "8899" in out)

    print("== serve + API ==")
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    lf = open(os.path.join(TMP, "srv.log"), "wb")
    proc = subprocess.Popen([PY, "-u", "-m", "clipkit", "serve", "--port", str(port),
                             "--no-semantic"], cwd=D, env=env, stdout=lf,
                            stderr=subprocess.STDOUT,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    def get(u):
        try:
            with urllib.request.urlopen(u, timeout=20) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()
    base = "http://127.0.0.1:%d" % port
    up = False
    for _ in range(40):
        time.sleep(0.4)
        try:
            st, b = get(base + "/api/health")
            if st == 200:
                up = True
                break
        except Exception:
            pass
    check("服务启动", up)
    if up:
        h = json.loads(b.decode("utf-8"))
        check("health 数据", h["frames"] == 72 and h["tags"] == 72 and h["subs"] == 6)
        st, page = get(base + "/")
        html = page.decode("utf-8")
        check("首页渲染", st == 200 and len(html) > 15000 and "__NFRAMES__" not in html)
        st, b2 = get(base + "/api/search?q=" + urllib.parse.quote("抱拳行礼") + "&top=3")
        d = json.loads(b2.decode("utf-8"))
        check("画面检索 API", st == 200 and len(d["results"]) == 3 and d["results"][0]["hits"])
        st, b2 = get(base + "/api/search?q=" + urllib.parse.quote("打沙袋") + "&top=2&timeline=1")
        d = json.loads(b2.decode("utf-8"))
        check("时间线 API", len(d.get("timeline", [])) > 0)
        st, b2 = get(base + "/api/subs?q=" + urllib.parse.quote("师父"))
        d = json.loads(b2.decode("utf-8"))
        check("台词 API", st == 200 and d.get("match") == "keyword")
        st, b2 = get(base + "/api/subs?q=" + urllib.parse.quote("师父"))
        check("台词缓存路径", st == 200)
        st, b2 = get(base + "/api/search?q=" + urllib.parse.quote("抱拳行礼") + "&top=3")
        d = json.loads(b2.decode("utf-8"))
        check("画面缓存路径", st == 200 and len(d["results"]) == 3)
        st, b2 = get(base + "/frames/DEMO_0001_f1.jpg")
        # 没装 Pillow 时 demo 不生成图，服务会返回占位 SVG —— 两种都算通过
        check("帧图可访问（缺图时返回占位图）", st == 200 and len(b2) > 50,
              "%d 字节" % len(b2))
    proc.terminate()
    time.sleep(0.3)
    lf.close()

    print("")
    print("===== clipkit 自测：PASS %d / FAIL %d =====" % (ok[0], fail[0]))
    return 1 if fail[0] else 0


if __name__ == "__main__":
    sys.exit(main())