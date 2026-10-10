# -*- coding: utf-8 -*-
"""各命令的实现。重依赖（torch / faster-whisper）缺失时给出可操作的提示，不静默失败。"""
import os, sys, csv, json, time, shutil, subprocess

from . import config as C
from . import store as S


def _say(*a):
    print(*a, flush=True)


def _need(mod, why, how):
    if C.has_module(mod):
        return True
    _say("[缺少依赖] " + mod + " —— " + why)
    _say("  安装： " + how)
    return False


# ---------------------------------------------------------------- init
def cmd_init(args):
    cfg = C.init(args.media, project=args.project, port=args.port, force=args.force)
    _say("[init] 配置已写入 " + cfg.path)
    _say("       项目根： " + cfg.root)
    for m in cfg.media_roots:
        _say("       素材目录： " + m + ("  ✓" if os.path.isdir(m) else "  ✗ 不存在"))
    _say("       帧目录： " + cfg.frames_dir)
    _say("")
    _say("下一步： clipkit doctor   （体检一下还缺什么）")
    return 0


# ---------------------------------------------------------------- doctor
def cmd_doctor(args):
    cfg = C.load()
    _say("=== clipkit " + __import__("clipkit").__version__ + " 体检 ===")
    _say("配置文件：" + cfg.path)
    _say("项目根  ：" + cfg.root)

    _say("--- 解释器 ---")
    _say("当前 Python：" + sys.executable)
    _say("版本       ：" + sys.version.split()[0])
    v = cfg.data.get("python_exe") or ""
    if v:
        ok = os.path.isfile(v)
        _say("项目解释器 ：" + v + ("  ✓" if ok else "  ✗ 不存在，跑 clipkit update --venv <路径>"))

    _say("--- 依赖 ---")
    # 项目配了解释器时，顺带探测它有没有装重依赖（用户实际会用那个跑）
    proj_has = {}
    if v and os.path.isfile(v):
        try:
            probe = ("import importlib.util as u,json;print(json.dumps({m: bool(u.find_spec(m)) "
                     "for m in [\"numpy\",\"PIL\",\"torch\",\"transformers\",\"faster_whisper\"]}))")
            pr = subprocess.run([v, "-c", probe], stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL, timeout=90)
            proj_has = json.loads(pr.stdout.decode("utf-8", "replace").strip().splitlines()[-1])
        except Exception:
            proj_has = {}
    for mod, why, how in (
        ("numpy", "向量检索的核心", "pip install numpy"),
        ("PIL", "抽帧和图片编码需要", "pip install pillow"),
        ("torch", "可选。装了才能做语义检索（画面相似度）", "pip install torch --index-url https://download.pytorch.org/whl/cu126"),
        ("transformers", "可选。中文-CLIP 模型加载", "pip install transformers"),
        ("faster_whisper", "可选。本地转写台词", "pip install faster-whisper"),
    ):
        has = C.has_module(mod)
        mark = "✓" if has else "✗"
        extra = ""
        if not has and proj_has.get(mod):
            mark = "✓*"
            extra = "   （项目解释器里已装，用 clipkit.json 里的 python_exe 跑即可）"
        _say("%-16s %s   %s%s" % (mod, mark, why, extra))

    _say("--- 素材 ---")
    roots = cfg.media_roots
    if not roots:
        _say("×  没配置素材目录")
    for r in roots:
        n = _count_media(r) if os.path.isdir(r) else -1
        _say("%s  %s  %s" % ("✓" if n >= 0 else "✗", r,
                              ("%d 个视频" % n) if n >= 0 else "目录不存在"))

    _say("--- 数据 ---")
    st = S.Store(cfg, load_vectors=C.has_module("numpy"), quiet=True)
    d = st.stats()
    _say("帧索引     ：%d 帧 / %d 条素材   %s" % (d["frames"], d["clips"],
                                                cfg.index_file if d["frames"] else "（还没建）"))
    _say("VLM 描述   ：%d 条%s" % (d["tags"], "" if d["tags"] else "   （还没跑 clipkit tag）"))
    _say("台词库     ：%d 条素材%s" % (d["subs"], "" if d["subs"] else "   （还没跑 clipkit transcribe）"))
    _say("帧图片目录 ：%s" % cfg.frames_dir)
    if os.path.isdir(cfg.frames_dir):
        n = sum(1 for x in os.listdir(cfg.frames_dir) if x.lower().endswith((".jpg", ".png")))
        _say("              %d 张图片" % n)

    _say("--- 能做什么 ---")
    can_img = d["frames"] > 0
    has_torch = C.has_module("torch") or proj_has.get("torch")
    has_tr = C.has_module("transformers") or proj_has.get("transformers")
    semantic = bool(can_img and has_torch and has_tr)
    keyword = d["tags"] > 0
    _say("画面语义检索 ：" + ("✓ 可用" if semantic else "✗ 需要 torch + transformers"))
    _say("画面关键词检索：" + ("✓ 可用（靠 VLM 描述）" if keyword else "✗ 需要先跑 clipkit tag"))
    _say("台词检索     ：" + ("✓ 可用" if d["subs"] else "✗ 需要先跑 clipkit transcribe"))
    ncat = sum(1 for x in d["categories"].values() if x)
    _say("分类筛选     ：" + ("✓ " + str(ncat) + " 个类别有数据" if keyword else "✗ 需要 VLM 描述"))

    if not (semantic or keyword):
        _say("提示：想先看看界面长什么样，跑  clipkit demo  造一份演示数据。")
    return 0


def _count_media(root):
    exts = (".mov", ".mp4", ".m4v", ".avi", ".mkv", ".mxf", ".wmv", ".flv")
    n = 0
    for dp, _, fs in os.walk(root):
        for f in fs:
            if f.lower().endswith(exts):
                n += 1
    return n
MEDIA_EXTS = (".mov", ".mp4", ".m4v", ".avi", ".mkv", ".mxf", ".wmv", ".flv")


FFMPEG_HINTS = [
    r"C:\ffmpeg\bin\ffmpeg.exe",
    r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
    "/opt/homebrew/bin/ffmpeg",
    "/usr/local/bin/ffmpeg",
    "/usr/bin/ffmpeg",
    "/snap/bin/ffmpeg",
]


def _find_ffmpeg():
    """ffmpeg: 先看配置，再看 PATH，再看各平台常见安装位置"""
    cfg = C.load(required=False)
    if cfg and cfg.data.get("ffmpeg") and os.path.isfile(cfg.data["ffmpeg"]):
        return cfg.data["ffmpeg"]
    p = shutil.which("ffmpeg")
    if p:
        return p
    for c in FFMPEG_HINTS:
        if os.path.isfile(c):
            return c
    return None


def _probe(ffprobe, path):
    """用 ffprobe 取时长/分辨率/帧率/编码"""
    if not ffprobe:
        return {}
    try:
        out = subprocess.run(
            [ffprobe, "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=width,height,r_frame_rate,codec_name",
             "-show_entries", "format=duration", "-of", "json", path],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=60)
        d = json.loads(out.stdout.decode("utf-8", "replace"))
    except Exception:
        return {}
    st = (d.get("streams") or [{}])[0]
    fmt = d.get("format") or {}
    return {"duration": float(fmt.get("duration") or 0),
            "width": st.get("width"), "height": st.get("height"),
            "fps": st.get("r_frame_rate", ""), "codec": st.get("codec_name", "")}


# ---------------------------------------------------------------- update
def cmd_update(args):
    cfg = C.load()
    changed = []
    if args.venv or args.python_exe:
        v = os.path.abspath(args.venv or args.python_exe)
        cfg.data["python_exe"] = v
        changed.append("python_exe=" + v)
    if args.media:
        cfg.data["media_roots"] = [os.path.abspath(m) for m in args.media]
        changed.append("media_roots=%d 个" % len(args.media))
    if args.port:
        cfg.data["port"] = int(args.port)
        changed.append("port=" + str(args.port))
    for kv in (args.set or []):
        if "=" not in kv:
            raise SystemExit("--set 需要 key=value 形式：" + kv)
        k, v = kv.split("=", 1)
        cur = cfg.data
        parts = k.split(".")
        for p in parts[:-1]:
            cur = cur.setdefault(p, {})
        try:
            v = json.loads(v)
        except Exception:
            pass
        cur[parts[-1]] = v
        changed.append(kv)
    if not changed:
        _say("没给任何要改的东西。用法示例：")
        _say("  clipkit update --venv \"D:/venv/Scripts/python.exe\"")
        _say("  clipkit update --port 8899")
        _say("  clipkit update --set ffmpeg=\"C:/ffmpeg/bin/ffmpeg.exe\"")
        return 1
    cfg.save()
    _say("[update] " + cfg.path)
    for c in changed:
        _say("   " + c)
    return 0


# ---------------------------------------------------------------- scan
def cmd_scan(args):
    cfg = C.load()
    roots = [r for r in cfg.media_roots if os.path.isdir(r)]
    if not roots:
        raise SystemExit("clipkit.json 里的素材目录都不存在。跑 clipkit update --media \"D:/素材\"")
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        cand = _find_ffmpeg()
        if cand:
            for name in ("ffprobe", "ffprobe.exe"):
                guess = os.path.join(os.path.dirname(cand), name)
                if os.path.isfile(guess):
                    ffprobe = guess
                    break
    if not ffprobe:
        ffprobe = shutil.which("ffprobe")
    if not ffprobe or not os.path.isfile(ffprobe):
        _say("[警告] 找不到 ffprobe，时长会记为 0（抽帧仍然可用，只是位置会落在开头）")

    found = []
    for root in roots:
        for dp, _, fs in os.walk(root):
            for f in fs:
                if f.lower().endswith(MEDIA_EXTS):
                    found.append(os.path.join(dp, f))
    found.sort()
    if args.limit:
        found = found[:args.limit]
    _say("[scan] 找到 %d 个视频，开始读取元数据…" % len(found))

    rows = []
    t0 = time.time()
    for i, p in enumerate(found, 1):
        info = _probe(ffprobe, p)
        name = os.path.basename(p)
        group = os.path.basename(os.path.dirname(p))
        rows.append({
            "file": name,
            "path": p,
            "group": group,
            "duration_sec": round(info.get("duration") or 0, 2),
            "width": info.get("width") or "",
            "height": info.get("height") or "",
            "fps": info.get("fps") or "",
            "codec": info.get("codec") or "",
            "size_MB": round(os.path.getsize(p) / 1048576.0, 1),
        })
        if i % 25 == 0 or i == len(found):
            sys.stdout.write("\r        进度 %d/%d  %.0fs" % (i, len(found), time.time() - t0))
            sys.stdout.flush()
    _say("")

    cfg.ensure_dirs()
    with open(cfg.media_csv, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else ["file"])
        w.writeheader()
        w.writerows(rows)
    total = sum(r["duration_sec"] for r in rows)
    _say("[scan] 共 %d 个视频 / %.1f 分钟素材 -> %s" % (len(rows), total / 60.0, cfg.media_csv))
    _say("下一步： clipkit frames")
    return 0


# ---------------------------------------------------------------- frames
def cmd_frames(args):
    cfg = C.load()
    if not os.path.isfile(cfg.media_csv):
        raise SystemExit("还没有素材清单，先跑：clipkit scan")
    ffmpeg = _find_ffmpeg()
    if not ffmpeg:
        raise SystemExit("找不到 ffmpeg。\n" +
                         "  macOS:  brew install ffmpeg\n" +
                         "  Ubuntu: sudo apt install ffmpeg\n" +
                         "  Windows: 下载后跑 clipkit update --set ffmpeg=\"C:/ffmpeg/bin/ffmpeg.exe\"")
    with open(cfg.media_csv, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    fracs = cfg.data.get("frame_fracs") or [0.2, 0.5, 0.8]
    width = int(cfg.data.get("frame_width") or 512)
    cfg.ensure_dirs()

    jobs = []
    for r in rows:
        stem = os.path.splitext(r["file"])[0]
        src = r.get("path") or ""
        if not src or not os.path.isfile(src):
            continue
        jobs.append((stem, src, float(r.get("duration_sec") or 0)))
    _say("[frames] %d 条素材 × %d 帧 = 预计 %d 张 -> %s"
         % (len(jobs), len(fracs), len(jobs) * len(fracs), cfg.frames_dir))

    from concurrent.futures import ThreadPoolExecutor, as_completed

    def grab(job):
        stem, src, dur = job
        made = 0
        for k, frac in enumerate(fracs, 1):
            out = os.path.join(cfg.frames_dir, "%s_f%d.jpg" % (stem, k))
            if os.path.exists(out) and os.path.getsize(out) > 1000 and not args.force:
                made += 1
                continue
            ts = max(0.0, dur * float(frac))
            for attempt in (0, 1):
                cmd = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
                       "-ss", "%.2f" % ts, "-i", src, "-frames:v", "1",
                       "-vf", "scale=%d:-1" % width, "-q:v", "4", out]
                try:
                    subprocess.run(cmd, check=True, timeout=120,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    if os.path.exists(out) and os.path.getsize(out) > 1000:
                        made += 1
                        break
                except Exception:
                    ts = 0.0
        return stem, made

    done = fails = 0
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as ex:
        futs = [ex.submit(grab, j) for j in jobs]
        for fu in as_completed(futs):
            try:
                stem, made = fu.result()
                done += 1
                if made == 0:
                    fails += 1
            except Exception:
                fails += 1
            if done % 10 == 0 or done == len(jobs):
                sys.stdout.write("\r        进度 %d/%d  失败 %d  %.0fs"
                                 % (done, len(jobs), fails, time.time() - t0))
                sys.stdout.flush()
    _say("")
    n = sum(1 for x in os.listdir(cfg.frames_dir) if x.lower().endswith(".jpg"))
    _say("[frames] 完成，目录里现在有 %d 张图（失败 %d 条素材）" % (n, fails))
    _say("下一步： clipkit index     建向量索引（需要 torch）")
    _say("    或： clipkit tag       用视觉大模型写描述（需要 API Key）")
    return 0
# ---------------------------------------------------------------- demo
DEMO_TOPICS = [
    ("抱拳行礼 武馆", "主体: 一位成年男性", "动作: 抱拳行礼", "场景: 室内武术训练馆",
     "画面: 近景；有手部特写；无器械", "抱拳, 行礼, 武馆, 师徒, 礼仪"),
    ("打沙袋 出拳", "主体: 两名年轻人", "动作: 用拳击打沙袋", "场景: 室内体育馆",
     "画面: 中景；有手部特写；有器械（沙袋）", "拳击, 沙袋, 出拳, 训练, 力量"),
    ("师父教学 讲解", "主体: 一位年长男性与三位年轻人", "动作: 示范讲解招式", "场景: 室内武术馆",
     "画面: 全景；无手部特写；无器械", "师父, 教学, 讲解, 示范, 传承"),
    ("拳谱 纸张文字", "主体: 一双手与一本线装书", "动作: 翻阅拳谱", "场景: 室内书桌",
     "画面: 特写；有手部特写；无器械", "拳谱, 书页, 文字, 史料, 纸张"),
    ("户外 广场 晨练", "主体: 十几位练功者", "动作: 集体练习太极拳", "场景: 城市广场",
     "画面: 全景；无手部特写；无器械", "广场, 户外, 晨练, 太极, 集体"),
    ("博物馆 展览 展品", "主体: 一位母亲与儿童", "动作: 观看展品", "场景: 博物馆内",
     "画面: 全景；无手部特写；有展品", "博物馆, 展览, 展品, 亲子, 室内"),
    ("木棍 器械 对练", "主体: 两名成年男性", "动作: 持棍对练", "场景: 室内训练场",
     "画面: 中景；有手部特写；有器械（木棍）", "木棍, 器械, 对练, 招式, 武术"),
    ("祠堂 祭祀 上香", "主体: 三位成年人", "动作: 上香祭拜", "场景: 祠堂内",
     "画面: 全景；无手部特写；无器械", "祠堂, 祭祀, 上香, 仪式, 传承"),
]


def _hsv_rgb(h, s, v):
    """极简 HSV->RGB，给 demo 占位图配色用"""
    import colorsys
    r, g, b = colorsys.hsv_to_rgb((h % 360) / 360.0, s, v)
    return (int(r * 255), int(g * 255), int(b * 255))


def cmd_demo(args):
    """造一份纯合成数据，用来验证整条链路（不需要素材、不需要模型、不需要网络）"""
    # numpy 尽量用；没有也能跑（向量不生成，退化为关键词检索，功能完整）
    np = None
    if C.has_module("numpy"):
        import numpy as np
    else:
        _say("[demo] 没装 numpy，跳过向量生成 —— 检索会退化为关键词模式（功能完整，效果略弱）")
        _say("       想要语义检索： pip install numpy")
    root = os.path.abspath(args.dir)
    os.makedirs(root, exist_ok=True)
    cfg = C.init([os.path.join(root, "media")], project=root, force=True)
    os.makedirs(os.path.join(root, "media"), exist_ok=True)
    if np is not None:
        rng = np.random.default_rng(20261011)
    else:
        import random as _random
        rng = _random.Random(20261011)
    DIM = 64

    # 每个主题一个「中心向量」，帧向量 = 中心 + 噪声 → 语义检索能真的命中相关主题
    centers = {}
    lexicon = {}
    _sum = lambda v: sum(x * x for x in v) ** 0.5
    for i, (topic, subj, act, scene, vis, kw) in enumerate(DEMO_TOPICS):
        if np is not None:
            c = rng.normal(0, 1, DIM)
            centers[topic] = (c / np.linalg.norm(c)).tolist()
        else:
            import random as _r
            _rnd = _r.Random(i * 7919)
            c = [_rnd.gauss(0, 1) for _ in range(DIM)]
            n = _sum(c) or 1.0
            centers[topic] = [x / n for x in c]
        for w in (kw.replace(" ", "").split(",") + [topic.replace(" ", "")]):
            if w:
                lexicon[w] = topic

    rows, vecs, taglines = [], [], []
    n_clip = 24
    for ci in range(n_clip):
        topic, subj, act, scene, vis, kw = DEMO_TOPICS[ci % len(DEMO_TOPICS)]
        clip = "DEMO_%04d" % (ci + 1)
        dur = round(6.0 + (ci % 7) * 2.5, 2)
        for k, frac in enumerate(cfg.data["frame_fracs"], 1):
            img = "%s_f%d.jpg" % (clip, k)
            if np is not None:
                base = centers[topic] + rng.normal(0, 0.28, DIM)
                vecs.append(base / np.linalg.norm(base))
            else:
                import random as _r
                _rnd = _r.Random(ci * 131 + k)
                v = [x + _rnd.gauss(0, 0.28) for x in centers[topic]]
                n = _sum(v) or 1.0
                vecs.append([x / n for x in v])
            rows.append({"img": img, "clip": clip, "frame": "f%d" % k,
                         "at": "%d%%" % int(frac * 100),
                         "approx_sec": "%.1fs" % (dur * frac),
                         "group": "demo", "dur": dur, "topic": topic})
            taglines.append({"clip": clip, "frame": "f%d" % k, "at": "%d%%" % int(frac * 100),
                             "approx_sec": "%.1fs" % (dur * frac), "group": "demo",
                             "dur": str(dur),
                             "desc": subj + chr(10) + act + chr(10) + scene + chr(10) + vis,
                             "tags": [kw] + [x.strip() for x in kw.split(",")], "ok": True})
    
    cfg.ensure_dirs()
    if np is not None:
        np.save(cfg.vectors_file, np.asarray(vecs, dtype="float32"))
    with open(cfg.index_file, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["img", "clip", "frame", "at", "approx_sec",
                                            "group", "dur", "topic"])
        w.writeheader()
        w.writerows(rows)
    with open(cfg.tags_file, "w", encoding="utf-8") as f:
        for t in taglines:
            f.write(json.dumps(t, ensure_ascii=False) + chr(10))
    with open(os.path.join(cfg.index_dir, "lexicon.json"), "w", encoding="utf-8") as f:
        json.dump(lexicon, f, ensure_ascii=False, indent=1)
    if np is not None:
        np.save(os.path.join(cfg.index_dir, "centers.npy"),
                np.asarray([centers[t] for t in [x[0] for x in DEMO_TOPICS]], dtype="float32"))
        np.save(os.path.join(cfg.index_dir, "vectors.npy"), np.asarray(vecs, dtype="float32"))

    # 台词样例
    subs = []
    lines = ["抱拳行礼，是武者的第一课", "师父说，这一招要练三百遍",
             "我不想放弃，我想继续练下去", "这门拳是我们历代祖师传下来的"]
    for ci in range(6):
        clip = "DEMO_%04d" % (ci + 1)
        segs = []
        for k, t in enumerate(lines):
            segs.append({"start": 1.0 + k * 3.2, "end": 1.0 + k * 3.2 + 2.6, "text": t})
        subs.append({"clip": clip, "ok": True, "dur": 14.6, "lang": "zh", "segments": segs})
    with open(cfg.transcripts_file, "w", encoding="utf-8") as f:
        for s in subs:
            f.write(json.dumps(s, ensure_ascii=False) + chr(10))

    # 占位图（纯色渐变，够用来验证界面布局）
    try:
        from PIL import Image, ImageDraw
        # 占位图做成有辨识度的渐变缩略图：不同主题不同色相，带编号，
        # 这样界面截图/肉眼核对都看得清，而不是一片纯色。
        topics = [t[0] for t in DEMO_TOPICS]
        for i, r0 in enumerate(rows):
            ti = topics.index(r0.get("topic", topics[0])) if r0.get("topic") in topics else i % len(topics)
            hue = (ti * 45) % 360
            top = _hsv_rgb(hue, 0.55, 0.30)
            bot = _hsv_rgb((hue + 40) % 360, 0.65, 0.72)
            im = Image.new("RGB", (320, 180))
            px = im.load()
            for y in range(180):
                t = y / 179.0
                c = tuple(int(top[k] + (bot[k] - top[k]) * t) for k in range(3))
                for x in range(320):
                    px[x, y] = c
            d = ImageDraw.Draw(im)
            for k in range(5):
                x0 = 18 + k * 62
                d.rectangle([x0, 132 - (k % 3) * 16, x0 + 40, 168],
                            outline=(255, 255, 255), width=2)
            d.text((12, 12), r0["clip"] + "  " + r0["frame"], fill=(255, 255, 255))
            im.save(os.path.join(cfg.frames_dir, r0["img"]), quality=82)
    except Exception as e:
        _say("[demo] 没装 Pillow，跳过占位图（不影响检索）：" + str(e))

    _say("[demo] 已在 " + root + " 造好演示数据")
    _say("       %d 帧 / %d 条素材 / %d 条描述 / %d 条台词" % (len(rows), n_clip, len(taglines), len(subs)))
    _say("下一步： clipkit --help 里挑一个，比如")
    _say("       cd " + root)
    _say("       clipkit query \"抱拳行礼\"")
    _say("       clipkit serve")
    return 0


# ---------------------------------------------------------------- query
def cmd_query(args):
    cfg = C.load()
    from .search import Searcher, Encoder
    st = S.Store(cfg, load_vectors=C.has_module("numpy"))
    enc = None
    if not args.no_semantic and C.has_module("torch"):
        cand = Encoder(cfg.data.get("clip_model"))
        want = st.vectors.shape[1] if getattr(st, "vectors", None) is not None else 0
        got = cand.dim() if want else None
        # 维度对不上（比如 demo 的合成向量）就别白加载几百 MB 模型
        if want and got is not None and got != want:
            print("[提示] 索引向量 %d 维，模型输出 %d 维，跳过模型加载，改走关键词检索" % (want, got))
        else:
            enc = cand
    srch = Searcher(st, enc)

    if args.subs:
        res, mode = srch.subs(args.q, top=args.top)
        if args.json:
            _say(json.dumps({"match": mode, "results": res}, ensure_ascii=False, indent=2))
            return 0
        if not res:
            _say("没有命中台词。")
            return 1
        _say("台词匹配（%s）：" % ("关键词" if mode == "keyword" else "语义近似"))
        for r in res:
            _say("  %s  全长 %.1fs" % (r["clip"], r["dur"]))
            for h in r["hits"][:5]:
                _say("     %6.1fs → %-6.1fs  %s" % (h["s"], h["e"], h["t"]))
        return 0

    res, meta = srch.frames(args.q, top=args.top, cats=None)
    if args.json:
        _say(json.dumps({"meta": meta, "results": res}, ensure_ascii=False, indent=2))
        return 0
    if not res:
        _say("没有结果。（模式：%s）" % meta.get("mode"))
        if st.n_frames == 0:
            _say("还没有索引。跑 clipkit scan / frames / index，或者 clipkit demo 先看看效果。")
        return 1
    _say("「%s」 %d 条（%s）" % (args.q, len(res),
                                "视觉+描述混合" if meta["mode"] == "hybrid" else "纯关键词"))
    _say("")
    for r in res:
        line = "  #%-2d %-14s %-4s %-6s  %s" % (r["rank"], r["clip"], r["frame"],
                                              r["approx_sec"] or r["at"], r["score"])
        _say(line)
        if r["keywords"]:
            _say("      " + " · ".join(r["keywords"][:5]))
        if r["hits"]:
            _say("      命中描述关键词：" + " / ".join(r["hits"]))
    return 0


# ---------------------------------------------------------------- serve
def cmd_serve(args):
    cfg = C.load()
    host = args.host or cfg.data.get("host") or "127.0.0.1"
    port = args.port or int(cfg.data.get("port") or 8777)
    from .web import serve
    return serve(cfg, host=host, port=int(port), semantic=not args.no_semantic)
# ---------------------------------------------------------------- index
def cmd_index(args):
    """用中文-CLIP 把每张帧图编码成向量，供语义检索用"""
    cfg = C.load()
    if not _need("numpy", "写向量索引", "pip install numpy"):
        return 1
    if not _need("torch", "画面语义检索核心",
                 "pip install torch --index-url https://download.pytorch.org/whl/cu126"):
        return 2
    if not _need("transformers", "中文-CLIP 模型", "pip install transformers"):
        return 2
    import csv as _csv
    import numpy as np
    import torch
    from PIL import Image
    from transformers import ChineseCLIPModel, ChineseCLIPProcessor

    frames_dir = cfg.frames_dir
    if not os.path.isdir(frames_dir):
        raise SystemExit("帧目录不存在：" + frames_dir + "\n先跑：clipkit frames")
    imgs = sorted(f for f in os.listdir(frames_dir)
                  if f.lower().endswith((".jpg", ".jpeg", ".png")) and "_Proxy" not in f)
    if not imgs:
        raise SystemExit("帧目录里没有图片：" + frames_dir)

    import re as _re
    media = {}
    if os.path.isfile(cfg.media_csv):
        with open(cfg.media_csv, encoding="utf-8-sig") as f:
            for r0 in _csv.DictReader(f):
                media[r0["file"].upper()] = r0
                media[os.path.splitext(r0["file"])[0].upper()] = r0

    fracs = cfg.data.get("frame_fracs") or [0.2, 0.5, 0.8]
    def frame_pos(fr, dur):
        m = _re.match(r"^f(\d+)$", fr or "")
        if not m or not dur:
            return ""
        i = int(m.group(1)) - 1
        if i < 0 or i >= len(fracs):
            return ""
        try:
            return "%.1fs" % (float(dur) * float(fracs[i]))
        except Exception:
            return ""

    dev = "cuda" if torch.cuda.is_available() else "cpu"

    print("[index] 设备 %s | 待编码 %d 张" % (dev, len(imgs)), flush=True)
    model = ChineseCLIPModel.from_pretrained(cfg.data["clip_model"]).to(dev).eval()
    proc = ChineseCLIPProcessor.from_pretrained(cfg.data["clip_model"])

    def pick(o):
        if torch.is_tensor(o):
            return o
        for k in ("image_embeds", "pooler_output"):
            v = getattr(o, k, None)
            if torch.is_tensor(v):
                return v
        return o.last_hidden_state[:, 0]

    V, rows = [], []
    t0 = time.time()
    bs = max(1, args.batch)
    with torch.no_grad():
        for i in range(0, len(imgs), bs):
            chunk = imgs[i:i + bs]
            pil = []
            for name in chunk:
                try:
                    pil.append(Image.open(os.path.join(frames_dir, name)).convert("RGB"))
                except Exception:
                    pil.append(Image.new("RGB", (224, 224)))
            inp = proc(images=pil, return_tensors="pt").to(dev)
            fv = pick(model.get_image_features(**inp)).float()
            fv = fv / fv.norm(dim=-1, keepdim=True)
            V.append(fv.cpu().numpy())
            for name in chunk:
                stem = os.path.splitext(name)[0]
                m = _re.match(r"^(.*)_(f\d+)$", stem)
                clip, fr = (m.group(1), m.group(2)) if m else (stem, "")
                info = media.get(clip.upper(), {})
                dur = info.get("duration_sec", "")
                at = ""
                mm = _re.match(r"^f(\d+)$", fr or "")
                if mm and 0 < int(mm.group(1)) <= len(fracs):
                    at = "%d%%" % int(float(fracs[int(mm.group(1)) - 1]) * 100)
                rows.append({"img": name, "clip": clip, "frame": fr, "at": at,
                             "approx_sec": frame_pos(fr, dur),
                             "group": info.get("group", ""), "dur": dur})
            done = min(i + bs, len(imgs))
            sys.stdout.write("\r        进度 %d/%d  %.0fs" % (done, len(imgs), time.time() - t0))
            sys.stdout.flush()
    print("")

    arr = np.concatenate(V).astype("float32")
    cfg.ensure_dirs()
    np.save(cfg.vectors_file, arr)
    with open(cfg.index_file, "w", newline="", encoding="utf-8-sig") as f:
        w = _csv.DictWriter(f, fieldnames=["img", "clip", "frame", "at", "approx_sec",
                                            "group", "dur"])
        w.writeheader()
        w.writerows(rows)
    print("[index] %s | 向量 %s | 耗时 %.0fs" % (cfg.index_file, arr.shape, time.time() - t0))
    print("下一步： clipkit serve")
    return 0
# ---------------------------------------------------------------- tag
VLM_PROVIDERS = {
    "zhipu": {"url": "https://open.bigmodel.cn/api/paas/v4/chat/completions",
              "key": "ZHIPUAI_API_KEY", "model": "glm-4v-flash"},
    "moonshot": {"url": "https://api.moonshot.cn/v1/chat/completions",
                 "key": "MOONSHOT_API_KEY", "model": "moonshot-v1-8k-vision-preview"},
    "ark": {"url": "https://ark.cn-beijing.volces.com/api/v3/chat/completions",
            "key": "ARK_API_KEY", "model": ""},
}

VLM_PROMPT = chr(10).join([
    "这是一段视频素材的截帧。请用简体中文客观描述画面，严格按以下格式输出，不要多余解释：",
    "主体: <画面上是谁/几个人，年龄性别>",
    "动作: <正在做什么具体动作>",
    "场景: <在哪里>",
    "画面: <景别 特写/近景/中景/全景/远景；有无手部特写；有无器械>",
    "关键词: <5个便于检索的中文词，逗号分隔>",
    "注意：只描述你确实看到的，看不清就写不确定，不要猜测。",
])


def cmd_tag(args):
    """用视觉大模型给每帧写中文描述 —— 混合排序、分类、描述都靠它"""
    cfg = C.load()
    import urllib.request, base64, io as _io
    if not os.path.isfile(cfg.index_file):
        raise SystemExit("还没有帧索引，先跑：clipkit index（或 clipkit demo 造演示数据）")
    vcfg = cfg.data.get("vlm") or {}
    prov = args.provider or vcfg.get("provider") or "zhipu"
    if prov not in VLM_PROVIDERS:
        raise SystemExit("不认识的 provider：" + prov)
    info = VLM_PROVIDERS[prov]
    key = os.environ.get(info["key"], "").strip()
    if not key:
        print("[缺少 API Key] 请先设置环境变量 " + info["key"])
        print("  例如： set " + info["key"] + "=你的key")
        return 2
    model = args.model or vcfg.get("model") or info["model"]
    if prov == "ark" and not model:
        raise SystemExit("火山方舟需要 endpoint id： clipkit update --set vlm.model=ep-xxxx")

    with open(cfg.index_file, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    done = set()
    if os.path.isfile(cfg.tags_file):
        with open(cfg.tags_file, encoding="utf-8") as f:
            for line in f:
                try:
                    d = json.loads(line)
                    if d.get("ok"):
                        done.add((d.get("clip"), d.get("frame")))
                except Exception:
                    pass
    todo = [r0 for r0 in rows if (r0.get("clip"), r0.get("frame")) not in done]
    if args.only:
        todo = [r0 for r0 in todo if r0.get("clip") == args.only]
    if args.limit:
        todo = todo[:args.limit]
    if not todo:
        print("[tag] 没有待处理的帧（已全部标注）")
        return 0
    print("[tag] provider=%s model=%s | 待标注 %d 帧 / 已有 %d 帧" % (prov, model, len(todo), len(done)))

    cfg.ensure_dirs()
    import threading
    from concurrent.futures import ThreadPoolExecutor, as_completed
    lock = threading.Lock()
    stat = {"ok": 0, "err": 0}
    workers = int(vcfg.get("workers") or 4)

    def one(r0):
        fp = os.path.join(cfg.frames_dir, r0["img"])
        if not os.path.isfile(fp):
            return r0, None, "图不存在"
        try:
            from PIL import Image
            im = Image.open(fp).convert("RGB")
            im.thumbnail((768, 768))
            buf = _io.BytesIO()
            im.save(buf, format="JPEG", quality=82)
            b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        except Exception as e:
            return r0, None, "读图失败 " + str(e)
        body = {"model": model, "messages": [{"role": "user", "content": [
            {"type": "text", "text": VLM_PROMPT},
            {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + b64}},
        ]}]}
        data = json.dumps(body).encode("utf-8")
        last = ""
        for attempt in range(3):
            try:
                req = urllib.request.Request(
                    info["url"], data=data,
                    headers={"Content-Type": "application/json",
                             "Authorization": "Bearer " + key})
                with urllib.request.urlopen(req, timeout=120) as resp:
                    d = json.loads(resp.read().decode("utf-8", "replace"))
                txt = d["choices"][0]["message"]["content"].strip()
                tags = []
                for line in txt.split(chr(10)):
                    if line.startswith("关键词"):
                        part = line.replace("：", ":").split(":", 1)[-1]
                        tags = [x.strip() for x in part.split(",") if x.strip()]
                return r0, {"clip": r0.get("clip", ""), "frame": r0.get("frame", ""),
                            "at": r0.get("at", ""), "approx_sec": r0.get("approx_sec", ""),
                            "group": r0.get("group", ""), "dur": r0.get("dur", ""),
                            "desc": txt,
                            "tags": ([", ".join(tags)] + tags) if tags else [],
                            "ok": True}, None
            except Exception as e:
                last = "%s: %s" % (type(e).__name__, str(e)[:120])
                time.sleep(1.5 * (attempt + 1))
        return r0, None, last

    t0 = time.time()
    with open(cfg.tags_file, "a", encoding="utf-8") as out, \
         ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(one, r0) for r0 in todo]
        n = 0
        for fu in as_completed(futs):
            r0, tag, err = fu.result()
            n += 1
            with lock:
                if tag:
                    out.write(json.dumps(tag, ensure_ascii=False) + chr(10))
                    out.flush()
                    stat["ok"] += 1
                else:
                    stat["err"] += 1
                    if stat["err"] <= 5:
                        print("   失败 %s: %s" % (r0.get("img"), err))
            if n % 10 == 0 or n == len(todo):
                sys.stdout.write("\r        进度 %d/%d 成功 %d 失败 %d %.0fs"
                                 % (n, len(todo), stat["ok"], stat["err"], time.time() - t0))
                sys.stdout.flush()
    print("")
    print("[tag] 完成：成功 %d / 失败 %d -> %s" % (stat["ok"], stat["err"], cfg.tags_file))
    print("下一步： clipkit serve（重启后描述与混合排序生效）")
    return 0


# ---------------------------------------------------------------- transcribe
def cmd_transcribe(args):
    """本地语音转写：素材音轨 -> 可检索中文台词库"""
    cfg = C.load()
    if not _need("faster_whisper", "本地转写", "pip install faster-whisper"):
        return 2
    if not os.path.isfile(cfg.media_csv):
        raise SystemExit("还没有素材清单，先跑：clipkit scan")
    ffmpeg = _find_ffmpeg()
    if not ffmpeg:
        raise SystemExit("找不到 ffmpeg，转写需要它抽音轨")
    model_size = args.model or cfg.data.get("whisper_model") or "small"
    with open(cfg.media_csv, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    done = set()
    if os.path.isfile(cfg.transcripts_file):
        with open(cfg.transcripts_file, encoding="utf-8") as f:
            for line in f:
                try:
                    d = json.loads(line)
                    if d.get("ok") and d.get("segments"):
                        done.add(d.get("clip"))
                except Exception:
                    pass
    todo = [r0 for r0 in rows
            if os.path.splitext(r0.get("file", ""))[0] not in done
            and r0.get("path") and os.path.isfile(r0["path"])]
    if args.limit:
        todo = todo[:args.limit]
    if not todo:
        print("[transcribe] 没有待转写的素材")
        return 0
    print("[transcribe] whisper=%s | 待转写 %d 条 / 已完成 %d 条" % (model_size, len(todo), len(done)))
    print("            首次会下载模型（约 0.5~1.5GB），走 hf-mirror 镜像")

    os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
    os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
    from faster_whisper import WhisperModel
    dev = "cpu"
    try:
        import torch
        dev = "cuda" if torch.cuda.is_available() else "cpu"
    except Exception:
        dev = "cpu"
    wm = WhisperModel(model_size, device=dev,
                      compute_type="float16" if dev == "cuda" else "int8")
    cfg.ensure_dirs()

    t0 = time.time()
    okn = errn = 0
    for i, r0 in enumerate(todo, 1):
        clip = os.path.splitext(r0["file"])[0]
        src = r0["path"]
        tmpwav = os.path.join(cfg.transcripts_dir, "_tmp.wav")
        try:
            subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
                            "-i", src, "-vn", "-ac", "1", "-ar", "16000",
                            "-f", "wav", tmpwav], check=True, timeout=1800)
            segs, info = wm.transcribe(tmpwav, language="zh", vad_filter=True)
            segments = [{"start": round(s.start, 2), "end": round(s.end, 2),
                         "text": (s.text or "").strip()}
                        for s in segs if (s.text or "").strip()]
            dur = round(float(getattr(info, "duration", 0) or 0), 2)
            rec = {"clip": clip, "ok": bool(segments), "dur": dur,
                   "lang": "zh", "segments": segments}
            with open(cfg.transcripts_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + chr(10))
            okn += 1
        except Exception as e:
            errn += 1
            if errn <= 5:
                print("   失败 %s: %s: %s" % (clip, type(e).__name__, str(e)[:100]))
        finally:
            try:
                if os.path.exists(tmpwav):
                    os.remove(tmpwav)
            except Exception:
                pass
        if i % 5 == 0 or i == len(todo):
            sys.stdout.write("\r        进度 %d/%d 成功 %d 失败 %d %.0fs"
                             % (i, len(todo), okn, errn, time.time() - t0))
            sys.stdout.flush()
    print("")
    print("[transcribe] 完成：成功 %d / 失败 %d -> %s" % (okn, errn, cfg.transcripts_file))
    print("下一步： clipkit serve（重启后台词检索生效）")
    return 0