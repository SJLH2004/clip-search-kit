# -*- coding: utf-8 -*-
"""HTTP 服务：把检索结果用网页呈现出来。

只用标准库 http.server，没有 Flask 这类依赖。
界面资源放在 ../templates/ 下，改完不用动 Python。
"""
import os, sys, json, time, threading, urllib.parse, mimetypes, collections
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

from . import __version__, store as S
from . import wordvec

HERE = os.path.dirname(os.path.abspath(__file__))
# 模板位置：优先包内 templates/（pip 安装后），回退到包外的 ../templates（源码/技能目录形态）
_CANDIDATES = [
    os.path.join(os.path.dirname(HERE), "templates"),                   # 源码 / 技能目录
    os.path.join(os.path.dirname(os.path.dirname(HERE)), "templates"),   # pip 安装（data-files）
    os.path.join(HERE, "templates"),                                     # 兼容旧布局
]
TPL = next((p for p in _CANDIDATES if os.path.isdir(p)), _CANDIDATES[-1])


def _read(name, fallback=""):
    p = os.path.join(TPL, name)
    try:
        with open(p, encoding="utf-8") as f:
            return f.read()
    except Exception:
        return fallback


PAGE = _read("app.html")
CSS = _read("app.css")
JS = _read("app.js")

IMG_CHIPS = ["手部特写", "抱拳行礼", "打沙袋 出拳", "师父教学 讲解",
             "一个人独自练拳", "两个人对练 推手", "武馆室内 训练场", "户外广场 晨练",
             "人脸特写 表情", "航拍 城市 俯瞰", "拳谱 纸张文字", "兵器 棍 刀",
             "器材 器械", "多人 集体 队列", "夜晚 户外 灯光", "博物馆 展览"]
SUB_CHIPS = ["师父", "训练", "坚持", "传承", "抱拳", "加油", "不想放弃", "谢谢"]


class App(object):
    def __init__(self, cfg, semantic=True):
        self.cfg = cfg
        self.st = S.Store(cfg, load_vectors=True, quiet=True)
        self.enc = None
        self.device = "关键词模式"
        if semantic:
            from .search import Encoder
            self.enc = Encoder(cfg.data.get("clip_model"))
            if self.enc.available() and self.st.vnorm is not None:
                print("[启动] 加载 Chinese-CLIP …", flush=True)
                t0 = time.time()
                if self.enc.load():
                    self.device = "GPU" if self.enc.device == "cuda" else "CPU"
                    print("[启动] 模型就绪 %.1fs（%s）" % (time.time() - t0, self.enc.device), flush=True)
            else:
                print("[启动] 没装 torch/transformers 或没有向量，走关键词模式", flush=True)
        from .search import Searcher
        self.srch = Searcher(self.st, self.enc)
        self.lock = threading.Lock()
        self.cache = collections.OrderedDict()
        self.stats = {"queries": 0, "zero": 0, "slow": 0, "started": time.time()}
        self.recent = collections.deque(maxlen=200)
        self.logfile = os.path.join(cfg.index_dir, "search_log.jsonl")

    # ---- 缓存 ----
    def cget(self, k):
        with self.lock:
            if k in self.cache:
                self.cache.move_to_end(k)
                return self.cache[k]
        return None

    def cput(self, k, v):
        with self.lock:
            self.cache[k] = v
            self.cache.move_to_end(k)
            while len(self.cache) > 128:
                self.cache.popitem(last=False)

    def note(self, q, ms, n, kind="frame"):
        self.stats["queries"] += 1
        if n == 0:
            self.stats["zero"] += 1
        if ms >= 300:
            self.stats["slow"] += 1
        rec = {"t": time.strftime("%Y-%m-%d %H:%M:%S"), "kind": kind, "q": q, "ms": ms, "n": n}
        self.recent.append(rec)
        try:
            with open(self.logfile, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + chr(10))
        except Exception:
            pass

    def history(self, limit=10):
        if not os.path.isfile(self.logfile):
            return []
        try:
            tail = collections.deque(maxlen=800)
            with open(self.logfile, encoding="utf-8") as f:
                for line in f:
                    tail.append(line)
            seen, out = set(), []
            for line in reversed(tail):
                try:
                    q = (json.loads(line).get("q") or "").strip()
                except Exception:
                    continue
                if q and q not in seen:
                    seen.add(q)
                    out.append(q)
                if len(out) >= limit:
                    break
            return out
        except Exception:
            return []

    # ---- 检索 ----
    def frames(self, q, top=12, dedup=True, cats=None, timeline=False):
        key = ("f", q, top, dedup, tuple(sorted(cats or [])), timeline)
        hit = self.cget(key)
        t0 = time.time()
        if hit is not None:
            data = hit
            ms = int((time.time() - t0) * 1000)
            self.note(q, ms, len(data.get("results") or []), "frame(cached)")
            return data, ms
        res, meta = self.srch.frames(q, top=top, dedup=dedup, cats=cats)
        # 无模型时的词表语义兜底（只有 demo 数据带 lexicon/centers，真实项目自动跳过）
        if meta.get("mode") == "keyword" and not self.srch.semantic and self.st.vnorm is not None:
            tv = wordvec.topic_vector(self.cfg, q)
            if tv is not None:
                import numpy as np
                sims = self.st.vnorm @ tv
                th = self.st.text_hits(S.terms_of(q))
                maxt = max([v[0] for v in th.values()], default=1.0)
                scored = []
                for i in sims.argsort()[::-1]:
                    r = self.st.rows[int(i)]
                    key = (r.get("clip", ""), r.get("frame", ""))
                    te = th.get(key, (0.0, []))
                    bonus = 0.10 * (te[0] / maxt) if maxt else 0.0
                    scored.append((float(sims[int(i)]) + bonus, float(sims[int(i)]), te[0], te[1], int(i)))
                    if len(scored) >= 700:
                        break
                res = self.srch._pack(scored, top, dedup)
                meta["mode"] = "hybrid(词表)"
        data = {"results": [self.enrich(r) for r in res], "meta": meta}
        if timeline:
            data["timeline"] = self.st.timeline(res)
        ms = int((time.time() - t0) * 1000)
        self.cput(key, data)
        self.note(q, ms, len(res), "frame")
        return data, ms

    def enrich(self, r):
        r = dict(r)
        r["subs"] = self.st.all_subs_for(r.get("clip", ""))
        return r

    def subs(self, q, top=20):
        key = ("s", q, top)
        t0 = time.time()
        hit = self.cget(key)
        if hit is not None:
            ms = int((time.time() - t0) * 1000)
            self.note(q, ms, len(hit[0]), "subs(cached)")
            return hit, ms
        out = self.srch.subs(q, top=top)          # (results, mode)
        ms = int((time.time() - t0) * 1000)
        self.cput(key, out)
        self.note(q, ms, len(out[0]), "subs")
        return out, ms

    # ---- 页面 ----
    def page(self):
        d = self.st.stats()
        page = "<!DOCTYPE html>" + chr(10) + "<html lang=\"zh-CN\"><head><meta charset=\"utf-8\">" + chr(10)
        page += "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">" + chr(10)
        page += "<title>素材语义检索 · clipkit</title>" + chr(10)
        page += "<style>" + chr(10) + CSS + chr(10) + "</style></head>" + chr(10) + "<body>" + chr(10)
        page += PAGE + chr(10) + "<script>" + chr(10) + JS.replace("</script>", "<\\/script>") + chr(10)
        page += "</script>" + chr(10) + "</body></html>" + chr(10)
        reps = {
            "__MODEL__": self.cfg.data.get("clip_model", "Chinese-CLIP"),
            "__DEVICE__": self.device,
            "__NFRAMES__": str(d["frames"]),
            "__NCLIPS__": str(d["clips"]),
            "__NTAGS__": str(d["tags"]),
            "__NSUBS__": str(d["subs"]),
            "__CHIPS__": json.dumps(IMG_CHIPS, ensure_ascii=False),
            "__SUBCHIPS__": json.dumps(SUB_CHIPS, ensure_ascii=False),
            "__CATS__": json.dumps(S.CATS, ensure_ascii=False),
            "__RECENT__": json.dumps(self.history(10), ensure_ascii=False),
        }
        for k, v in reps.items():
            page = page.replace(k, v)
        return page.encode("utf-8")

    # ---- 静态文件 ----
    def frame_file(self, name):
        return os.path.join(self.cfg.frames_dir, name)

    def media_file(self, name):
        roots = self.cfg.media_roots
        for root in roots:
            p = os.path.join(root, name)
            if os.path.isfile(p):
                return p
        for root in roots:
            for dp, _, fs in os.walk(root):
                if name in fs:
                    return os.path.join(dp, name)
        return None

class Handler(BaseHTTPRequestHandler):
    app = None
    server_version = "clipkit/" + __version__
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        sys.stderr.write("[%s] %s" % (time.strftime("%H:%M:%S"), fmt % args))

    def _send(self, code, ctype, body, extra=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
            pass

    def _json(self, code, obj):
        self._send(code, "application/json; charset=utf-8",
                   json.dumps(obj, ensure_ascii=False).encode("utf-8"))

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        path = urllib.parse.unquote(u.path)
        app = self.app

        if path in ("/", "/index.html"):
            self._send(200, "text/html; charset=utf-8", app.page())
            return

        if path == "/api/health":
            d = app.st.stats()
            self._json(200, dict(d, ok=True,
                                 mode=("hybrid" if app.srch.semantic else "keyword"),
                                 device=app.device, version=__version__,
                                 uptime_sec=int(time.time() - app.stats["started"]),
                                 stats=app.stats))
            return

        if path == "/api/_diag":
            import traceback
            out = {}
            try:
                v = app.subs("师父", top=2)
                out["type"] = str(type(v))
                out["len"] = len(v)
                out["elements"] = [str(type(x)) for x in v]
                out["element0_repr"] = repr(v[0])[:200]
                try:
                    (res, mode), ms = v
                    out["unpack"] = "ok mode=" + mode
                except Exception as e:
                    out["unpack"] = type(e).__name__ + ": " + str(e)
            except Exception:
                out["error"] = traceback.format_exc()[-600:]
            self._json(200, out)
            return

        if path == "/api/stats":
            self._json(200, dict(app.stats, recent=list(app.recent)[-60:]))
            return

        if path == "/api/search":
            qs = urllib.parse.parse_qs(u.query)
            q = (qs.get("q", [""])[0]).strip()
            try:
                top = max(1, min(int(qs.get("top", ["12"])[0]), 60))
            except ValueError:
                top = 12
            dedup = qs.get("dedup", ["1"])[0] != "0"
            want_tl = qs.get("timeline", ["0"])[0] == "1"
            cats = [c for c in (qs.get("cats", [""])[0]).split("|") if c in S.CATS] or None
            if not q:
                self._json(200, {"results": [], "ms": 0, "meta": {}})
                return
            try:
                data, ms = app.frames(q, top=top, dedup=dedup, cats=cats, timeline=want_tl)
            except Exception as e:
                self._json(500, {"error": str(e), "results": [], "meta": {}})
                return
            out = {"query": q, "ms": ms, "results": data["results"],
                   "meta": data.get("meta", {})}
            if want_tl:
                out["timeline"] = data.get("timeline", [])
            self._json(200, out)
            return

        if path == "/api/subs":
            qs = urllib.parse.parse_qs(u.query)
            q = (qs.get("q", [""])[0]).strip()
            try:
                top = max(1, min(int(qs.get("top", ["20"])[0]), 60))
            except ValueError:
                top = 20
            if not q:
                self._json(200, {"results": [], "ms": 0})
                return
            try:
                (res, mode), ms = app.subs(q, top=top)
            except Exception as e:
                self._json(500, {"error": str(e), "results": []})
                return
            hint = ""
            if mode == "semantic":
                hint = "没有字面命中，下面是语义最接近的台词（仅供参考）"
            elif not res:
                hint = "台词库里没有这个词，可以换成画面检索试试"
            self._json(200, {"query": q, "ms": ms, "results": res, "match": mode,
                             "meta": {"hint": hint}})
            return

        if path.startswith("/frames/"):
            self._file(app.frame_file(os.path.basename(path[len("/frames/"):])))
            return

        if path.startswith("/media/"):
            p = app.media_file(os.path.basename(path[len("/media/"):]))
            self._file(p, stream=True)
            return

        self._send(404, "text/plain; charset=utf-8", b"not found")

    def _file(self, fp, stream=False):
        if not fp or not os.path.isfile(fp):
            self._send(404, "text/plain; charset=utf-8", b"not found")
            return
        ctype = mimetypes.guess_type(fp)[0] or "application/octet-stream"
        size = os.path.getsize(fp)
        rng = self.headers.get("Range")
        if stream and rng and rng.startswith("bytes="):
            try:
                a, _, b = rng[6:].partition("-")
                start = int(a) if a else 0
                end = int(b) if b else size - 1
                end = min(end, size - 1)
                if start > end or start >= size:
                    raise ValueError
            except ValueError:
                self.send_response(416)
                self.send_header("Content-Range", "bytes */%d" % size)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            length = end - start + 1
            self.send_response(206)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(length))
            self.send_header("Content-Range", "bytes %d-%d/%d" % (start, end, size))
            self.send_header("Accept-Ranges", "bytes")
            self.end_headers()
            try:
                with open(fp, "rb") as f:
                    f.seek(start)
                    left = length
                    while left > 0:
                        chunk = f.read(min(262144, left))
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                        left -= len(chunk)
            except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
                pass
            return
        with open(fp, "rb") as f:
            body = f.read()
        extra = {"Cache-Control": "public, max-age=86400"}
        if stream:
            extra["Accept-Ranges"] = "bytes"
        self._send(200, ctype, body, extra)

    def do_HEAD(self):
        self.do_GET()


def serve(cfg, host="127.0.0.1", port=8777, semantic=True):
    app = App(cfg, semantic=semantic)
    Handler.app = app
    d = app.st.stats()
    print("")
    print("  素材语义检索 · clipkit " + __version__)
    print("  索引：%d 帧 / %d 条素材 · 描述 %d 条 · 台词 %d 条"
          % (d["frames"], d["clips"], d["tags"], d["subs"]))
    mode = ("视觉语义 + 描述混合" if app.srch.semantic
            else "关键词（装了 torch 可开启语义检索）")
    print("  模式：" + mode)
    print("  打开： http://%s:%d" % (host, port))
    print("")
    srv = ThreadingHTTPServer((host, int(port)), Handler)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("已停止。")
    finally:
        srv.server_close()
    return 0