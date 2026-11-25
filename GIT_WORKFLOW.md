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

在项目目录修改并验证。使用 `git status` 和 `git diff` 审核改动，只暂存本次需要提交的源码、静态资源或文档。提交说明用 `类型: 简短描述` 格式，例如 `feat: 新增地点多选筛选`、`fix: 修复站点计数` 或 `docs: 更新部署说明`。

```bash
git add README.md
git diff --cached --check
git commit -m "docs: 更新部署说明"
# 需要发布时再推送：
git push origin master
```

`.venv/`、`__pycache__/`、日志和 SQLite 数据库是本地运行产物。真实令牌、密码、私钥和服务端 `/etc/charger-monitor.env` 不应进入版本库。

## Docker Compose 发布与回退

只打包已提交的版本。以下命令在仓库根目录的 Bash 中运行（Windows 可用 Git Bash），把 `deploy-user@server` 换成实际 SSH 登录账号和地址：

```bash
release=$(git rev-parse --short=12 HEAD)
git archive --format=tar.gz --output="charger-monitor-$release.tar.gz" HEAD
scp "charger-monitor-$release.tar.gz" deploy-user@server:~
```

在服务器上将包解压到新的版本目录，例如 `/opt/charger-monitor/releases/<提交号>`；目录须由有权限的用户创建，不覆盖旧版本。进入该版本目录，把 `RELEASE_TAG` 设置为这次打包用的提交号，按 [Docker Compose 部署指南](deploy/README.md#docker-compose) 构建、试跑并验收。Compose 项目名固定，启动新版会替换同一个服务，不会另开一个采样实例。

验收失败时，先用 `docker compose logs --no-color > rollout-error.log` 保存日志。如果有旧版，进入旧版本目录，确认其 `.env` 和镜像仍在，再执行 `docker compose up -d --no-build --pull never`。如果是首次部署且没有旧版，则从本次版本目录执行 `docker compose down`。回退后重新检查 `/api/health` 和网页。

## Ubuntu / Debian systemd 更新
首次部署按 [云端部署指南](deploy/README.md) 克隆本仓库。以后在服务器更新工作副本，不直接编辑 `/opt/charger-monitor` 里的运行副本：

```bash
cd ~/charger-monitor
git pull --ff-only origin master
sudo bash deploy/deploy.sh
curl -fsS http://127.0.0.1:8765/api/health
systemctl status charger-monitor --no-pager
```

部署脚本同步代码并重启服务，保留 `/etc/charger-monitor.env` 和旧版数据库文件。当前服务不读取旧数据库，重启后需等待采样。
