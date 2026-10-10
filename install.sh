#!/usr/bin/env bash
# clipkit 一键安装：复制技能到常见 agent 的 skills 目录，可选装基础依赖
# 用法： ./install.sh
#        ./install.sh --target ~/.claude/skills
#        ./install.sh --deps
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NAME="clip-search-kit"
TARGET=""
WANT_DEPS=0

while [ $# -gt 0 ]; do
  case "$1" in
    --target) TARGET="$2"; shift 2 ;;
    --deps)   WANT_DEPS=1; shift ;;
    -h|--help) sed -n "2,6p" "$0"; exit 0 ;;
    *) echo "未知参数: $1" >&2; exit 2 ;;
  esac
done

PY="$(command -v python3 || command -v python || true)"
if [ -z "$PY" ]; then
  echo "没找到 python3，请先安装 Python 3.9+" >&2
  exit 127
fi
echo "Python: $($PY --version 2>&1)"

if [ "$WANT_DEPS" = "1" ]; then
  echo "安装基础依赖（numpy / pillow）…"
  "$PY" -m pip install --user numpy pillow
fi

if [ -z "$TARGET" ]; then
  for cand in "$HOME/.claude/skills" "$HOME/.workbuddy/skills" "$HOME/.config/clipkit/skills"; do
    if [ -d "$cand" ]; then TARGET="$cand"; break; fi
  done
fi
if [ -z "$TARGET" ]; then
  TARGET="$HOME/.local/share/clipkit/skills"
  echo "没检测到已知 skills 目录，使用默认：$TARGET"
fi

DEST="$TARGET/$NAME"
mkdir -p "$TARGET"
if [ -e "$DEST" ]; then
  echo "已存在 $DEST，备份为 $DEST.bak"
  rm -rf "$DEST.bak"
  mv "$DEST" "$DEST.bak"
fi
mkdir -p "$DEST"
for item in SKILL.md INSTRUCTIONS.md PORTABILITY.md manifest.json pyproject.toml clipkit templates gui.py selftest.py start.sh 启动器.py; do
  if [ -e "$HERE/$item" ]; then cp -r "$HERE/$item" "$DEST/"; fi
done
echo "已安装到 $DEST"

echo ""
echo "要做的事："
echo "  1) 装进 Python 环境（可选，之后任意目录可用）："
echo "       cd $DEST"
echo "       $PY -m pip install --user --no-deps ."
echo "  2) 验证（零依赖自测）："
echo "       $PY $DEST/selftest.py"
echo "  3) 开始用："
echo "       $PY -m clipkit demo my-demo"
echo "       cd my-demo && $PY -m clipkit serve"
