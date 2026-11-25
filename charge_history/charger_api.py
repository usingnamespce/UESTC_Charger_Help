"""读取上游充电口状态和当前已充分钟数。"""

from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

# ══════════════════════════════════════════════════════════
#  网络配置
# ══════════════════════════════════════════════════════════
PROXIES          = {"http": None, "https": None}
TIMEOUT          = 10

# ══════════════════════════════════════════════════════════
#  请求头
# ══════════════════════════════════════════════════════════
HEADERS = {
    "sec-ch-ua-platform": "\"Android\"",
    "sec-ch-ua": "\"Chromium\";v=\"142\", \"Android WebView\";v=\"142\", \"Not_A Brand\";v=\"99\"",
    "systemphone": "Android 16",
    "sec-ch-ua-mobile": "?1",
    "brands": "2407FRK8EC",
    "user-agent": (
        "Mozilla/5.0 (Linux; Android 16; 2407FRK8EC Build/BP2A.250605.031.A3; wv) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Mobile Safari/537.36"
    ),
    "content-type": "application/json;charset=utf-8",
    # "token": "YOUR_TOKEN_HERE",
    "accept": "*/*",
    "origin": "https://api.issks.com",
    "x-requested-with": "com.tencent.mm",
    "sec-fetch-site": "same-site",
    "sec-fetch-mode": "cors",
    "sec-fetch-dest": "empty",
    "referer": "https://api.issks.com/",
    "accept-encoding": "gzip, deflate, br, zstd",
    "accept-language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
    "priority": "u=1, i",
}

STATUS_FREE    = 1
STATUS_BUSY    = 2
STATUS_BROKEN  = 3
KNOWN_STATUSES = (STATUS_FREE, STATUS_BUSY, STATUS_BROKEN)


def fetch_outlet_duration(outlet_no):
    """返回已充分钟数；缺失、无效或查询失败时返回 None。"""
    url = "https://wemp.issks.com/charge/v1/charging/outlet/{}".format(outlet_no)
    try:
        resp = requests.get(url, headers=HEADERS, proxies=PROXIES, timeout=TIMEOUT)
        if resp.status_code != 200:
            return None
        body = resp.json()
        data = body.get("data")
        if str(body.get("code")) != "1" or not isinstance(data, dict):
            return None
        used_min = int(data.get("usedmin"))
        return used_min if used_min >= 0 else None
    except (requests.RequestException, TypeError, ValueError, AttributeError):
        return None


def fetch_station(station_id):
    """查询单站充电口；只为正在充电的插座额外查询时长。"""
    url = "https://wemp.issks.com/charge/v1/outlet/station/outlets/{}".format(station_id)
    try:
        resp = requests.get(url, headers=HEADERS, proxies=PROXIES, timeout=TIMEOUT)
        if resp.status_code != 200:
            return None
        body = resp.json()
        rows = body.get("data")
        if str(body.get("code")) != "1" or not isinstance(rows, list):
            return None

        outlets = []
        busy = []
        for row in rows:
            status = int(row.get("currentChargingRecordId") or STATUS_BROKEN)
            outlet = {
                "serial": int(row.get("outletSerialNo") or 0),
                "status": status if status in KNOWN_STATUSES else STATUS_BROKEN,
                "used_min": None,
            }
            outlets.append(outlet)
            if outlet["status"] == STATUS_BUSY and row.get("outletNo"):
                busy.append((row["outletNo"], outlet))

        if busy:
            with ThreadPoolExecutor(max_workers=min(len(busy), 6)) as executor:
                futures = {executor.submit(fetch_outlet_duration, number): outlet for number, outlet in busy}
                for future in as_completed(futures):
                    futures[future]["used_min"] = future.result()
        return outlets
    except (requests.RequestException, TypeError, ValueError, AttributeError) as exc:
        print(f"[API] 站点 {station_id} 请求失败: {exc}")
        return None
