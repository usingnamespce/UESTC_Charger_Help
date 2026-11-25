# charge_history（核心模块）

这个目录是**整个项目的主体**：后端采样 + 历史库 + HTTP 接口 + 手机网页前端。

## 文件说明

| 文件 | 作用 |
|---|---|
| `charge_history_backend.py` | 采样清单中的站点，写入 SQLite，并提供 HTTP 接口和网页；默认每轮结束后等待 60 秒 |
| `charger_api.py` | 调「闪开来电」(issks) 接口取站点/插座数据 |
| [`all.json`](all.json) | 采样清单（`站点名 -> station_id`） |
| `charge_history.db` | 默认生成的 SQLite 数据库，不提交到 Git |
| `station_locations.json` | 各站经纬度和地址（由 `/api/locations` 提供，静态分布图不依赖此表） |
| `station_overrides.json` | 手动坐标校正（可选；源数据个别站坐标错时用） |
| `export_locations.py` | 生成 / 刷新 `station_locations.json` |
| `web/` | 手机网页前端（站点列表、插座、充电历史和静态分布图） |
| [`web/charger-map.jpg`](web/charger-map.jpg) | 充电桩分布图，由现有 HTTP 服务直接托管 |

## 采样范围和地点分类

采样范围以 `all.json`（或启动参数 `--stations` 指定的清单）为准，不按地址或经纬度自动搜索。新增站点前先确认平台的 `station_id`，修改采样清单后重启后端。`station_locations.json` 是独立的坐标表，条目和数量不必与采样清单一致；只更新坐标不会把站点加入采样。

在 [`web/station_keywords.txt`](web/station_keywords.txt) 中每行填写一个地点关键词。列表按站点原名包含的关键词归组，匹配时忽略空白以及大小写、全半角差异；多个关键词命中时使用最长的一个，同长度时按配置中的先后顺序。没有命中的站点归入「未分类」，不会修改站点原名。修改配置后刷新网页即可生效。

## 接口一览

- `GET /api/health` — 服务状态；在 `data.collector.last_summary` 查看最近一轮采样结果
- `GET /api/stations` — 站点列表（空闲/充电中/故障汇总；`ending_soon_count` 为最近一次采样时仍在充电、且已充超过 7 小时 45 分钟的充电口数）
- `GET /api/outlets?station_id=<ID>` — 站点充电口状态；`current_session_start` 和 `last_seen_at` 用于计算已充时长
- `GET /api/sessions?station_id=<ID>&outlet_no=<编号>&days=3` — 某充电口的充电历史
- `GET /api/session?session_id=<ID>` — 单次充电会话详情
- `GET /api/locations` — 站点坐标
- `GET /api/admin/collect` — 手动触发一次采样（需管理口令）

## 本地检查

在仓库根目录安装依赖后，可用以下命令检查网页和接口，不发起自动采样：

```bash
python charge_history/charge_history_backend.py --no-collector
```

访问 `http://127.0.0.1:8765/api/health` 检查服务。空数据库下站点列表为空，属正常情况。完整启动和部署步骤见[项目说明](../README.md)。
