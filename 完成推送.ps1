# 完成 clipkit 仓库的推送（交互式，双击 完成推送.cmd 或右键运行本文件）
$ErrorActionPreference = "Continue"
$env:Path = $env:Path + ";C:Users时间轮回AppDataLocalProgramsPortableGitcmd"
$REPO = "C:Users时间轮回WorkBuddyclip-search-kit-repo"
Set-Location -LiteralPath $REPO

function Line($t, $c = "Gray") { Write-Host $t -ForegroundColor $c }

Line "" 
Line "===============================================" Cyan
Line "  clipkit 仓库推送助手" Cyan
Line "===============================================" Cyan
Line ""
Line ("仓库: " + $REPO)
Line ("当前提交身份: " + (git config user.name) + " <" + (git config user.email) + ">")
Line ("提交数: " + (git rev-list --count HEAD))
Line ""

Line "[1/3] 提交身份（会公开显示在 commit 历史里）" Yellow
Line "      用 GitHub 账号绑定的邮箱最保险；不想暴露真实邮箱可用："
Line "      用户名 <12345678+用户名@users.noreply.github.com>"
$nm = Read-Host "      姓名"
$em = Read-Host "      邮箱"
if ([string]::IsNullOrWhiteSpace($nm) -or [string]::IsNullOrWhiteSpace($em)) { Line "已取消（姓名或邮箱为空）" Red; exit 1 }
git config user.name $nm | Out-Null
git config user.email $em | Out-Null
git commit --amend --reset-author --no-edit -q
Line ("      已设为: " + $nm + " <" + $em + ">") Green

Line ""
Line "[2/3] GitHub 信息" Yellow
$user = Read-Host "      GitHub 用户名"
if ([string]::IsNullOrWhiteSpace($user)) { Line "用户名不能为空。" Red; exit 1 }
$name = Read-Host "      仓库名（回车默认 clip-search-kit）"
if ([string]::IsNullOrWhiteSpace($name)) { $name = "clip-search-kit" }
$url = "https://github.com/$user/$name.git"
git remote remove origin 2>$null | Out-Null
git remote add origin $url
Line ("      已配置 origin -> " + $url) Green

Line ""
Line "[3/3] 创建仓库并推送" Yellow
Line "      即将打开 GitHub 的建仓页面 —— 关键：不要勾选 Add README / .gitignore / license，"
Line "      要建一个完全空的仓库，否则首次推送会被拒（下面有补救提示）。"
Line ""
Start-Process "https://github.com/new?name=$name"
Line "      第一次推送会弹出登录窗口，用浏览器授权即可。"
Read-Host "      仓库建好后按回车开始推送"
Line ""
git push -u origin main

if ($LASTEXITCODE -eq 0) {
  Line ""
  Line "推送成功！" Green
  Line ("仓库地址: https://github.com/" + $user + "/" + $name) Green
} else {
  Line ""
  Line "推送被拒。先自动诊断原因…" Red
  $remoteHas = git ls-remote origin 2>$null
  if ($remoteHas) {
    Line ""
    Line "原因：远端仓库不是空的（你可能勾选了 Add README 等）。" Red
    Line "两种解法，任选其一：" Yellow
    Line ""
    Line "  解法 A（推荐）：删掉刚建的空仓库，重新建一个不带 README 的" Cyan
    Line "          Settings -> 拉到最底 Delete this repository，然后重跑本脚本"
    Line ""
    Line "  解法 B：把远端那个 README 合并进来，再推" Cyan
    $ans = Read-Host "          现在自动执行解法 B 吗？(y/N)"
    if ($ans -eq "y") {
      git pull --no-rebase --no-edit --allow-unrelated-histories origin main
      git push -u origin main
      if ($LASTEXITCODE -eq 0) { Line "处理完成，推送成功！" Green } else { Line "仍未成功，请把上面的报错发我。" Red }
    }
  } else {
    Line ""
    Line "远端还是空的，那可能是：登录被取消 / 仓库名拼错 / 没网络。" Yellow
    Line "检查一下仓库名是不是 https://github.com/$user/$name" Yellow
  }
}
Line ""
Read-Host "按回车关闭"
