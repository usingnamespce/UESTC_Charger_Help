# charge_history（核心模块）

这个目录是**整个项目的主体**：后端采样、内存快照、HTTP 接口和手机网页。

## 文件说明

| 文件 | 作用 |
|---|---|
| `charge_history_backend.py` | 采样清单中的站点，只在内存中保留每站最近一次成功采样；默认每轮结束后等待 60 秒 |
| `charger_api.py` | 调「闪开来电」(issks) 接口取站点/插座数据 |
| [`all.json`](all.json) | 采样清单（`站点名 -> station_id`） |
| `web/` | 手机网页前端（站点列表、充电口状态和静态分布图） |
| [`web/charger-map.jpg`](web/charger-map.jpg) | 充电桩分布图，由现有 HTTP 服务直接托管 |

## 采样范围和地点分类

采样范围以 `all.json`（或启动参数 `--stations` 指定的清单）为准，不按地址或经纬度自动搜索。新增站点前先确认平台的 `station_id`，修改采样清单后重启后端。

在 [`web/station_keywords.txt`](web/station_keywords.txt) 中每行填写一个地点关键词。列表按站点原名包含的关键词归组，匹配时忽略空白以及大小写、全半角差异；多个关键词命中时使用最长的一个，同长度时按配置中的先后顺序。没有命中的站点归入「未分类」，不会修改站点原名。修改配置后刷新网页即可生效。

## 快照与接口

每轮结束后一起发布数据。浏览器只读内存，不会触发上游请求。未首次采样、采样失败，以及上游确认没有充电口是不同状态。某站采样失败时，保留上次成功时间，不把旧状态用于可用性筛选。重启后从空快照开始，不读写旧版 SQLite 文件。

- `GET /api/health` — 服务状态；在 `data.collector.last_summary` 查看最近一轮采样结果
- `GET /api/stations` — 采样清单中的站点、`sample_status`、`last_seen_at` 和充电口计数。只有状态为 `ready` 时有计数；`ending_soon_count` 统计仍在充电且已充超过 465 分钟的充电口。
- `GET /api/outlets?station_id=<ID>` — 当前站点的状态和 `outlets`；充电口只有编号、状态和 `used_min`（已充分钟数，不明时为 `null`）。站点状态非 `ready` 时 `outlets` 为空。
- `GET /api/admin/collect` — 手动触发一次采样（需管理口令）

## 本地检查

在仓库根目录安装依赖后，可用以下命令检查网页和接口，不发起自动采样：

```bash
python charge_history/charge_history_backend.py --no-collector
```

访问 `http://127.0.0.1:8765/api/health` 检查服务。关闭自动采样时，初始状态为「未开启自动采样，暂无数据」。完整启动和部署步骤见[项目说明](../README.md)。
