# 把这个仓库传上 GitHub

> **本机没装 git**（我确认过：`git`、`git.exe`、`gh` 都不在，Program Files / scoop / tools 下也没有）。
> 所以下面的命令需要你装好 git 后自己执行 —— 仓库文件已经全部就绪，就差提交。
>
> Windows 装 git：https://git-scm.com/download/win（或 `winget install Git.Git`）

## 一次性准备

```bash
cd clip-search-kit
git init -b main
git add -A
git commit -m "feat: clipkit 1.0.0 —— 视频素材中文语义检索"

# 在 GitHub 上新建一个空仓库（不要勾选 README/.gitignore），然后：
git remote add origin https://github.com/<you>/clip-search-kit.git
git push -u origin main
```

## 建议的仓库设置

| 项 | 建议值 |
|---|---|
| Description | 把一目录视频素材变成「说人话就能找到画面和台词」的本地检索服务 · 可作 AI skill |
| Topics | `video` `semantic-search` `clip` `chinese` `ai-skill` `footage` `ffmpeg` `whisper` `local-first` `editing` |
| License | MIT（仓库已含 LICENSE） |
| 首页预览 | 建议开 Pages，或在 README 顶部保留 `docs/demo-search.png` |

## 发布 release（可选）

```bash
git tag v1.0.0
git push origin v1.0.0
```

然后可以在 GitHub Releases 里附上打包好的 zip，方便别人直接下载：

```bash
# 生成可分发压缩包（排除开发用文件）
git archive --format=zip -o clip-search-kit-1.0.0.zip HEAD
```

## CI

`.github/workflows/ci.yml` 已在仓库里，推上去会自动跑：

- 3 个系统（Ubuntu / Windows / macOS）× 2 个 Python 版本（3.9 / 3.12）
- **先跑零依赖自测**（这是新用户的第一体验，不能被依赖问题破坏）
- 再装 numpy + pillow 跑一次
- 最后验证 `pip install` 与 `clipkit --version`

## 上传前自查

```bash
python selftest.py                 # 应当全绿
python -m clipkit doctor           # 确认没夹带个人路径
git status --short                 # 确认没有 clipkit.json / .clipkit/ 被提交
```

`.gitignore` 已经排除了运行产物（`clipkit.json`、`.clipkit/`、`素材帧/`），
这些是跟素材绑定的数据，不该进仓库。