# Ubuntu / Debian 云端部署

## 安装并启动

使用可访问充电平台接口的 Ubuntu 或 Debian 服务器。登录服务器后执行：

```bash
sudo apt-get update
sudo apt-get install -y git rsync
git clone -b master https://github.com/usingnamespce/UESTC_Charger_Help.git ~/charger-monitor
cd ~/charger-monitor
sudo bash deploy/deploy.sh
```

脚本创建 `charger` 服务用户，把应用同步到 `/opt/charger-monitor`，安装 Python 虚拟环境和依赖，并启用 `charger-monitor` systemd 服务。

```bash
curl -fsS http://127.0.0.1:8765/api/health
systemctl status charger-monitor --no-pager
journalctl -u charger-monitor -n 50 --no-pager
```

健康接口返回 `ok: true` 表示服务可查询。首次部署还要等第一轮采样结束；在 `collector.last_summary` 中检查 `station_ok` 和 `station_failed`。

## 访问方式与防火墙

- **仅供可信网络直连**：服务单元默认监听 `0.0.0.0:8765`。在系统防火墙及云安全组仅向需要访问的可信网段放行 TCP `8765`，浏览器打开 `http://<服务器地址>:8765/`。
- **公网访问**：建议使用 Caddy + 域名提供 HTTPS，后端仍用本机 HTTP，不对外开放 TCP `8765`。把域名解析到服务器，在云安全组和系统防火墙放行 TCP `80`、`443`。

### 使用 Caddy 反向代理

安装 Caddy。将 [Caddyfile.example](Caddyfile.example) 中对应的站点块复制到 `/etc/caddy/Caddyfile`，按需去掉注释并替换域名。已有站点时合并配置，不要覆盖其他站点。

使用 `sudo systemctl edit charger-monitor` 新建服务覆盖配置，加入：

```ini
[Service]
ExecStart=
ExecStart=/opt/charger-monitor/.venv/bin/python charge_history_backend.py --host 127.0.0.1 --port 8765
```

```bash
sudo systemctl restart charger-monitor
sudo caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
sudo systemctl enable --now caddy
sudo systemctl reload caddy
```

从外部验证 HTTPS 地址后，确认未向公网放行 `8765`。所示 `systemctl edit` 配置独立于仓库自带的服务单元，重新部署时不需要再次修改。

## 管理接口与数据

查询接口和网页无需登录。`/api/admin/collect` 只在同时配置 `CHARGER_AUTH_USER` 和 `CHARGER_AUTH_PASS` 时可用；未配置时返回 `403`。新部署生成的 `/etc/charger-monitor.env` 默认只示例、不启用账号。若旧安装还使用示例账号和密码，应立即取消配置或更换为独立强密码。

确需启用时，在服务器上编辑该环境文件并重启服务；通过 HTTPS 或服务器本机访问管理接口。`CHARGER_RATE_LIMIT` 和 `CHARGER_RATE_WINDOW` 仅用于管理接口，默认每个来源 IP 在 60 秒内允许 30 次；普通查询不受此限制。

最新状态只保存在内存，重启后等待第一轮新采样；不需要新建数据库或数据卷。升级时不读取或改写旧数据库文件。如有自定义启动参数，移除旧版的 `--db` 和 `--retention-days`。站点清单是 `charge_history/all.json`；网页静态地图是 `charge_history/web/charger-map.jpg`。

更新步骤见 [Git 提交与发布流程](../GIT_WORKFLOW.md#更新服务器)。
