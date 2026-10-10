# -*- coding: utf-8 -*-
"""配置：clipkit.json 的读写，以及解释器自举。"""
import json, os, sys, shutil

CFG_NAME = "clipkit.json"

DEFAULTS = {
    "project": ".",
    "media_roots": [],
    "dirs": {
        "frames": "素材帧",
        "index": ".clipkit/index",
        "tags": ".clipkit/tags",
        "transcripts": ".clipkit/transcripts",
    },
    "frame_fracs": [0.2, 0.5, 0.8],
    "frame_width": 512,
    "clip_model": "OFA-Sys/chinese-clip-vit-base-patch16",
    "whisper_model": "small",
    "host": "127.0.0.1",
    "port": 8777,
    "vlm": {"provider": "zhipu", "model": "glm-4v-flash", "workers": 4},
}


def cfg_path(start=None):
    """从 start（默认当前目录）向上找 clipkit.json"""
    d = os.path.abspath(start or os.getcwd())
    while True:
        p = os.path.join(d, CFG_NAME)
        if os.path.isfile(p):
            return p
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent


def deep_merge(base, over):
    out = dict(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


class Config(object):
    def __init__(self, data, path):
        self.data = data
        self.path = path
        self.root = os.path.dirname(os.path.abspath(path))

    def path_of(self, key):
        d = self.data.get("dirs", {})
        return os.path.normpath(os.path.join(self.root, d.get(key, key)))

    @property
    def frames_dir(self):
        return self.path_of("frames")

    @property
    def index_dir(self):
        return self.path_of("index")

    @property
    def tags_dir(self):
        return self.path_of("tags")

    @property
    def transcripts_dir(self):
        return self.path_of("transcripts")

    @property
    def media_roots(self):
        out = []
        for r in self.data.get("media_roots") or []:
            out.append(os.path.normpath(r if os.path.isabs(r) else os.path.join(self.root, r)))
        return out

    @property
    def vectors_file(self):
        return os.path.join(self.index_dir, "vectors.npy")

    @property
    def index_file(self):
        return os.path.join(self.index_dir, "index.csv")

    @property
    def tags_file(self):
        return os.path.join(self.tags_dir, "tags.jsonl")

    @property
    def transcripts_file(self):
        return os.path.join(self.transcripts_dir, "transcripts.jsonl")

    @property
    def media_csv(self):
        return os.path.join(self.index_dir, "media_index.csv")

    def ensure_dirs(self):
        for d in (self.frames_dir, self.index_dir, self.tags_dir, self.transcripts_dir):
            os.makedirs(d, exist_ok=True)

    def save(self):
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
            f.write("\n")

    def __repr__(self):
        return "<Config %s root=%s>" % (self.path, self.root)


HELP_MISSING = ("找不到 clipkit.json。先在这个项目的根目录跑一次初始化：\n"
                "    python -m clipkit init --media \"D:/你的素材目录\"\n"
                "（路径用正斜杠或双反斜杠都行）")


def load(start=None, required=True):
    p = cfg_path(start)
    if not p:
        if required:
            raise SystemExit(HELP_MISSING)
        return None
    with open(p, encoding="utf-8") as f:
        data = json.load(f)
    return Config(deep_merge(DEFAULTS, data), p)


def init(media_roots, project=None, port=None, force=False):
    root = os.path.abspath(project or os.getcwd())
    p = os.path.join(root, CFG_NAME)
    if os.path.exists(p) and not force:
        raise SystemExit("已经存在 " + p + "（要覆盖加 --force）")
    data = deep_merge(DEFAULTS, {"media_roots": [os.path.abspath(m) for m in media_roots]})
    if port:
        data["port"] = int(port)
    os.makedirs(root, exist_ok=True)
    cfg = Config(data, p)
    cfg.ensure_dirs()
    cfg.save()
    return cfg


def find_python():
    """优先当前解释器，其次 PATH 上的 python/py"""
    exe = sys.executable
    if exe and os.path.isfile(exe):
        return exe
    for name in ("python", "python3", "py"):
        p = shutil.which(name)
        if p:
            return p
    return None


def has_module(name):
    import importlib.util
    try:
        return importlib.util.find_spec(name) is not None
    except Exception:
        return False
