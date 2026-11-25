# 电子科技大学充电桩查询

查询电子科技大学清水河校区充电桩的**空闲情况和已充时长**。数据来自「闪开来电」，页面显示的是最近一次采样结果。

**项目来源：** 本项目基于 [ganhaidong/UESTC_Charger_Monitor 的 `master` 分支](https://github.com/ganhaidong/UESTC_Charger_Monitor/tree/master) 二次开发。本项目提供定时采样、按地点分组的站点列表及静态充电桩分布图。

## 一、网页使用（手机 / 电脑）

- **地点**：没有保存过偏好时，默认选中全部地点。点「选择地点」可搜索和勾选地点，浏览器会记住自定义选择；点「全选」恢复默认。
- **状态**：左侧「空闲」默认选中，只显示至少有一个空闲充电口的站点；右侧「全部」显示所选地点的所有站点。两种状态均支持按站点名称搜索。
- **充电口**：点站点查看各充电口状态。充电中的卡片显示已充时长；上游未返回时长时显示「时长未知」。不保存历史、金额或功率。
- **地图**：点「地图」查看静态充电桩分布图，点「查看原图」可放大。图片只在打开地图时下载，充电口状态以列表为准。
- **刷新**：后端每轮采样完成后默认等待 60 秒再开始下一轮；网页的「刷新」和「自动刷新」只读取内存中的最新采样，不触发新一轮采样。采样失败的站点不会算作空闲，可在「全部」中查看失败提示和上次成功时间。

## 二、本地运行与部署

### 2.1 本机运行

安装 Python 3，在项目根目录执行。Windows PowerShell：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe charge_history\charge_history_backend.py
```

macOS / Linux：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python charge_history/charge_history_backend.py
```

默认只监听本机，浏览器打开 `http://127.0.0.1:8765/`；可访问 `/api/health` 检查服务。每次启动后等待第一轮采样。服务不需要数据库或数据卷。升级旧版时，原有 SQLite 文件不会被修改或删除，也不再读取。只想检查网页和接口时，可加 `--no-collector` 关闭自动采样。

### 2.2 局域网访问与常用参数

- 让同一局域网的设备访问时，在启动命令末尾加 `--host <本机局域网IPv4>`，用实际地址替换占位符；在防火墙上仅允许可信网段入站访问 TCP `8765`，然后从其他设备打开 `http://<本机局域网IPv4>:8765/`。
- `start_server.bat`（Windows）和 `start_server.command`（macOS）会监听所有 IPv4 网卡（`0.0.0.0`）；仅在需要共享且已设置防火墙时使用。
- `--port` 可改端口；`--sample-interval` 可调整轮次之间的等待秒数。

### 2.3 云端部署

- **Docker Compose（推荐）：** 适用于 Linux x86_64（包括 Alibaba Cloud Linux）。构建、验收和首次启动步骤见 [Docker Compose 部署指南](deploy/README.md#docker-compose)。启动后，从允许访问的设备打开 `http://<服务器IP>:8765/`，无需域名或登录。直连是明文 HTTP，管理接口默认关闭。
- **Ubuntu / Debian systemd：** 也可运行 `sudo bash deploy/deploy.sh`，具体步骤及 HTTPS 反代配置见 [systemd 部署指南](deploy/README.md#ubuntu--debian-systemd-部署)。两种方式选其一，避免端口冲突和重复采样。

静态地图随应用部署。访问 `/api/health` 不仅要检查接口是否可响应，还要等 `data.collector.last_summary` 出现并确认采样成功；重启后需要重新采样。

## 三、维护与验证

- [核心模块与接口](charge_history/README.md)：采样清单、地点关键词、内存快照和 API 的说明。
- [Git 提交与发布流程](GIT_WORKFLOW.md)：提交格式和服务器更新步骤。
- 在项目根目录使用已安装依赖的 Python 运行 `python -m unittest discover -s tests -v`，测试使用模拟采样，不请求上游。

## 四、致谢

- 直接上游：[ganhaidong/UESTC_Charger_Monitor](https://github.com/ganhaidong/UESTC_Charger_Monitor/tree/master)。
- 原始工具：[WGooold/UESTC_Charger_Monitor](https://github.com/WGooold/UESTC_Charger_Monitor)。
- 数据接口由「闪开来电」（issks）充电平台提供。
