import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DEVICE_TABLE = {
    "SOIL_01": {"name": "Cảm biến đất khu A", "metrics": ["soil_moisture", "temperature"]},
    "WEATHER_01": {"name": "Trạm thời tiết", "metrics": ["temperature", "humidity"]},
    "PUMP_01": {"name": "Bơm tưới khu A", "metrics": ["flow_rate", "power"]},
    "PH_01": {"name": "Cảm biến pH bồn", "metrics": ["ph"]},
    "TANK_01": {"name": "Bồn nước chính", "metrics": ["level"]},
    "SUN_01": {"name": "Cảm biến nắng khu A", "metrics": ["lux"]},
}

GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def colorize(text, code):
    if not sys.stdout.isatty():
        return text
    return f"{code}{text}{RESET}"


def load_captures(paths):
    records = []
    for path in paths:
        p = Path(path)
        if p.is_dir():
            files = sorted(p.glob("*.jsonl"))
        elif p.is_file():
            files = [p]
        else:
            print(colorize(f"[!] Không tìm thấy: {p}", RED))
            continue
        for f in files:
            try:
                with open(f, encoding="utf-8") as fh:
                    for line in fh:
                        line = line.strip()
                        if line:
                            records.append(json.loads(line))
            except Exception as e:
                print(colorize(f"[!] Lỗi đọc {f}: {e}", RED))
    return records


def analyze(records):
    by_device = defaultdict(list)
    non_json = 0
    unknown = defaultdict(int)
    topics = defaultdict(int)
    for rec in records:
        device = rec.get("device_code")
        if rec.get("raw_payload"):
            non_json += 1
        topics[rec.get("mqtt_topic", "?")] += 1
        if device:
            by_device[device].append(rec)
        else:
            unknown[rec.get("mqtt_topic", "?")] += 1
    return by_device, non_json, unknown, topics


def report(records):
    by_device, non_json, unknown, topics = analyze(records)
    total = len(records)
    print("=" * 72)
    print(colorize("PHÂN TÍCH DỮ LIỆU BẮT ĐƯỢC (đối chiếu bảng thiết bị đề bài)", BOLD))
    print("=" * 72)
    print(f"Tổng bản tin      : {total}")
    print(f"Bản tin không JSON: {non_json}")
    print(f"Topic đã thấy     : {len(topics)}")
    for topic, count in sorted(topics.items()):
        print(f"  - {topic}  ({count} msg)")

    print("\n" + colorize("KẾT QUẢ TỪNG THIẾT BỊ:", BOLD))
    seen = 0
    for code, info in DEVICE_TABLE.items():
        recs = by_device.get(code, [])
        if recs:
            seen += 1
            first = datetime.fromtimestamp(recs[0]["capture_time"]).strftime("%H:%M:%S")
            last = datetime.fromtimestamp(recs[-1]["capture_time"]).strftime("%H:%M:%S")
            present_metrics = set()
            samples = {}
            for r in recs:
                for metric in info["metrics"]:
                    if metric in r.get("payload", {}):
                        present_metrics.add(metric)
                        samples.setdefault(metric, r["payload"][metric])
            missing = [m for m in info["metrics"] if m not in present_metrics]
            status = colorize("ĐỦ metric", GREEN)
            if missing:
                status = colorize(f"THIẾU: {', '.join(missing)}", YELLOW)
            print(colorize(f"  [X] {code} ({info['name']}) - {len(recs)} msg | {first} -> {last}", GREEN))
            print(f"        Metric: {', '.join(info['metrics'])} | {status}")
            print(f"        Mẫu giá trị: {json.dumps(samples, ensure_ascii=False)}")
        else:
            print(colorize(f"  [ ] {code} ({info['name']}) - KHÔNG CÓ DỮ LIỆU", RED))

    if unknown:
        print("\n" + colorize("THIẾT BỊ KHÔNG NHẬN DIỆN ĐƯỢC (cần xem xét):", BOLD))
        for topic, count in sorted(unknown.items()):
            print(colorize(f"  [!] {topic} - {count} msg", RED))

    print("\n" + colorize("KẾT LUẬN:", BOLD))
    if seen >= 4:
        print(colorize(f"  ĐẠT {seen}/6 thiết bị (yêu cầu >= 4/6) - đủ điều kiện chấm điểm.", GREEN))
    else:
        print(colorize(f"  CHƯA ĐẠT: {seen}/6 thiết bị (yêu cầu >= 4/6).", RED))
        print("  Hành động: hỏi BTC topic thật, hoặc chờ data chảy, hoặc kiểm tra format payload.")
    print("=" * 72)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Phân tích file capture JSONL của mqtt_probe, đối chiếu với 6 thiết bị trong đề bài.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("paths", nargs="*", help="File .jsonl hoặc thư mục capture (mặc định: Smurf/data/captures)")
    parser.add_argument("--capture-dir", default=str(Path(__file__).resolve().parent.parent / "data" / "captures"), help="Thư mục capture mặc định")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    paths = args.paths or [args.capture_dir]
    records = load_captures(paths)
    if not records:
        print(colorize("Không có dữ liệu để phân tích. Chạy mqtt_probe.py trước để bắt dữ liệu.", YELLOW))
        sys.exit(1)
    report(records)