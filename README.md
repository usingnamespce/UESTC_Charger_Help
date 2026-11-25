# 电子科技大学充电桩查询

查询电子科技大学清水河校区充电桩的**空闲情况和充电历史**。数据来自「闪开来电」。

**项目来源：** 本项目基于 [ganhaidong/UESTC_Charger_Monitor 的 `master` 分支](https://github.com/ganhaidong/UESTC_Charger_Monitor/tree/master) 二次开发。在其网页、地图和采样功能的基础上，本项目新增了按地点归组、地点多选筛选和记住已选地点。

## 一、给普通用户：怎么用（手机 / 电脑浏览器）

打开网址（部署后，例如 `http://…:8765/`）：

- **列表**：先点 **选择地点**，搜索或勾选一个或多个地点；只显示所选地点的站点，首次打开不默认选择，浏览器会记住选择。默认只显示有空闲充电口的站点，点 **全部** 可查看所选地点的所有站点，也可按站点名称搜索。点 **即将结束** 可筛出至少有一个充电口已充超过 7 小时 45 分钟、且最近一次采样时仍在充电的站点。点站点查看插座，再点插座看近 3 天的充电记录与功率曲线。
- 后端每轮采样完成后默认等待 60 秒再开始下一轮。网页右上角的「自动刷新」单独控制页面刷新，也可以点「刷新」手动读取已采集的数据。

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

默认只监听本机，浏览器打开 `http://127.0.0.1:8765/`；可访问 `/api/health` 检查服务。首次启动后等待第一轮采样完成再查看站点。仓库已带站点坐标表，只有需要更新坐标时才运行 `charge_history/export_locations.py`。

### 2.2 局域网访问与常用参数

- 让同一局域网的设备访问时，在启动命令末尾加 `--host <本机局域网IPv4>`，用实际地址替换占位符；在防火墙上仅允许可信网段入站访问 TCP `8765`，然后从其他设备打开 `http://<本机局域网IPv4>:8765/`。
- `start_server.bat`（Windows）和 `start_server.command`（macOS）会监听所有 IPv4 网卡（`0.0.0.0`）；仅在需要共享且已设置防火墙时使用。
- `--port` 可改端口；`--sample-interval` 可调整轮次之间的等待秒数；`--no-collector` 只启动网页和查询接口，不请求实时数据。

### 2.3 云端部署

Ubuntu / Debian 上可运行 `sudo bash deploy/deploy.sh`，由 systemd 托管。公网部署、反向代理和管理接口配置见 [云端部署指南](deploy/README.md)。

## 三、致谢

- 直接上游：[ganhaidong/UESTC_Charger_Monitor](https://github.com/ganhaidong/UESTC_Charger_Monitor/tree/master)。
- 原始工具：[WGooold/UESTC_Charger_Monitor](https://github.com/WGooold/UESTC_Charger_Monitor)。
- 数据接口由「闪开来电」（issks）充电平台提供。

## 四、未来优化
- 要是每个充电桩位置都有实景拍照就好了，这样就能通过照片辨认充电桩的实际位置。（实地拍照可能需要大家共同的努力）
- 欢迎大家提意见和建议，或贡献代码。
