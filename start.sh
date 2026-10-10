#!/usr/bin/env bash
# clipkit 启动器（macOS / Linux）
# 用法： ./start.sh            自动挑界面
#        ./start.sh --menu    控制台菜单
#        ./start.sh --web     直接起服务并开浏览器
set -e
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8
export PYTHONPATH="$HERE${PYTHONPATH:+:$PYTHONPATH}"

# 优先用虚拟环境里的 python
PY=""
for cand in "$HERE/.venv/bin/python" "$(command -v python3 || true)" "$(command -v python || true)"; do
  if [ -n "$cand" ] && [ -x "$cand" ]; then PY="$cand"; break; fi
done

if [ -z "$PY" ]; then
  echo "没找到 python3。请先安装 Python 3.9 或更高版本。" >&2
  exit 127
fi

exec "$PY" "$HERE/启动器.py" "$@"
