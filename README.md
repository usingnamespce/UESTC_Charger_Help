# 电子科技大学充电桩查询

查询电子科技大学清水河校区充电桩的**空闲情况、已充时长和充电历史**。数据来自「闪开来电」，页面显示的是最近一次采样结果。

**项目来源：** 本项目基于 [ganhaidong/UESTC_Charger_Monitor 的 `master` 分支](https://github.com/ganhaidong/UESTC_Charger_Monitor/tree/master) 二次开发。本项目保留采样和充电历史功能，将页面简化为按地点分组的站点列表，不再显示地图。

## 一、网页使用（手机 / 电脑）

- **地点**：没有保存过偏好时，默认选中全部地点。点「选择地点」可搜索和勾选地点，浏览器会记住自定义选择；点「全选」恢复默认。
- **状态**：「空闲」是默认筛选，只显示至少有一个空闲充电口的站点。「全部」显示所选地点的所有站点；可同时按站点名称搜索。
- **即将结束**：只要一个站点有至少一个充电口在最近一次采样时仍在充电，且已充**超过 7 小时 45 分钟**，该站点就会入选。恰好达到阈值不算，也不保证插座会在某个时间空出。
- **充电口和历史**：点站点查看各充电口状态，充电中的卡片显示已充时长，不显示金额和功率。再点充电口可查看近 3 天的充电记录与功率曲线。
- **刷新**：后端每轮采样完成后默认等待 60 秒再开始下一轮；网页的「刷新」和「自动刷新」只读取已采集的数据，不触发新一轮采样。

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

默认只监听本机，浏览器打开 `http://127.0.0.1:8765/`；可访问 `/api/health` 检查服务。首次启动后等待第一轮采样完成再查看站点。只想检查网页和接口时，可加 `--no-collector` 关闭自动采样。

### 2.2 局域网访问与常用参数

- 让同一局域网的设备访问时，在启动命令末尾加 `--host <本机局域网IPv4>`，用实际地址替换占位符；在防火墙上仅允许可信网段入站访问 TCP `8765`，然后从其他设备打开 `http://<本机局域网IPv4>:8765/`。
- `start_server.bat`（Windows）和 `start_server.command`（macOS）会监听所有 IPv4 网卡（`0.0.0.0`）；仅在需要共享且已设置防火墙时使用。
- `--port` 可改端口；`--sample-interval` 可调整轮次之间的等待秒数。

### 2.3 云端部署

Ubuntu / Debian 上可运行 `sudo bash deploy/deploy.sh`，由 systemd 托管。公网部署、反向代理和管理接口配置见 [云端部署指南](deploy/README.md)。

## 三、维护与验证

- [核心模块与接口](charge_history/README.md)：采样清单、地点关键词、SQLite 和 API 的说明。
- [Git 提交与发布流程](GIT_WORKFLOW.md)：提交格式和服务器更新步骤。
- 在项目根目录使用已安装依赖的 Python 运行 `python -m unittest discover -s tests -v`，测试使用临时 SQLite 数据库，不请求上游。

## 四、致谢

- 直接上游：[ganhaidong/UESTC_Charger_Monitor](https://github.com/ganhaidong/UESTC_Charger_Monitor/tree/master)。
- 原始工具：[WGooold/UESTC_Charger_Monitor](https://github.com/WGooold/UESTC_Charger_Monitor)。
- 数据接口由「闪开来电」（issks）充电平台提供。
