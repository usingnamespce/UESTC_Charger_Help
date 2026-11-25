# Git 提交与发布流程

## 仓库与分支

本项目基于 [ganhaidong/UESTC_Charger_Monitor 的 `master` 分支](https://github.com/ganhaidong/UESTC_Charger_Monitor/tree/master) 二次开发。当前仓库的默认分支是 `master`。

- `origin`：`https://github.com/usingnamespce/UESTC_Charger_Help.git`，本项目的提交和发布仓库。
- `upstream`（可选）：`https://github.com/ganhaidong/UESTC_Charger_Monitor.git`，用于查看直接上游的改动；上游历史与本项目的提交历史分开维护。

```bash
git remote -v
# 仅在需要查看上游时添加一次：
git remote add upstream https://github.com/ganhaidong/UESTC_Charger_Monitor.git
git fetch upstream
```

## 本地提交

在项目目录修改并验证。使用 `git status` 和 `git diff` 审核改动，只暂存本次需要提交的源码、静态资源或文档。提交说明用一句话概括改动，例如 `新增地点多选筛选`。

```bash
git add README.md
git diff --cached --check
git commit -m "更新部署说明"
# 需要发布时再推送：
git push origin master
```

`.venv/`、`__pycache__/`、日志和 SQLite 数据库是本地运行产物。真实令牌、密码、私钥和服务端 `/etc/charger-monitor.env` 不应进入版本库。

## 更新服务器

首次部署按 [云端部署指南](deploy/README.md) 克隆本仓库。以后在服务器更新工作副本，不直接编辑 `/opt/charger-monitor` 里的运行副本：

```bash
cd ~/charger-monitor
git pull --ff-only origin master
sudo bash deploy/deploy.sh
curl -fsS http://127.0.0.1:8765/api/health
systemctl status charger-monitor --no-pager
```

部署脚本同步代码并重启服务，保留已有的数据库和 `/etc/charger-monitor.env`。
