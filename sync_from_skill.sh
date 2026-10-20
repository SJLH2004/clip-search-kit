#!/usr/bin/env bash
# 从技能包（真相源）同步到本仓库，保留仓库专属文件
# 用法： ./sync_from_skill.sh [技能包路径]
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="${1:-$HOME/.workbuddy/skills/clip-search-kit}"

if [ ! -d "$SRC" ]; then
  echo "找不到技能包：$SRC" >&2
  echo "用法： ./sync_from_skill.sh /path/to/clip-search-kit" >&2
  exit 2
fi

echo "从 $SRC 同步到 $HERE"

# 代码与界面
for item in clipkit templates; do
  rm -rf "$HERE/$item"
  cp -r "$SRC/$item" "$HERE/$item"
  echo "  -> $item"
done

# 单文件
for f in SKILL.md INSTRUCTIONS.md PORTABILITY.md PROVENANCE.md manifest.json pyproject.toml \
         selftest.py gui.py start.sh 启动器.py 启动.bat LICENSE; do
  if [ -e "$SRC/$f" ]; then cp -f "$SRC/$f" "$HERE/$f"; echo "  -> $f"; fi
done

# 清理缓存
find "$HERE" -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true

# 仓库专属文件（不从技能包覆盖）：README / CHANGELOG / CONTRIBUTING / .github / docs / install.sh
echo ""
echo "保留仓库专属：README.md CHANGELOG.md CONTRIBUTING.md .github/ docs/ install.sh"
echo ""
echo "同步完成。验证："
echo "    cd $HERE && python selftest.py"