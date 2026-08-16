import json
import time
import urllib.request
from kafka import KafkaProducer

# 3 Tọa độ Nông nghiệp thật tại Việt Nam
FARMS = [
    {
        "farm_id": "FARM_DALAT_01",
        "name": "Nông trại Rau Củ Công nghệ cao Đà Lạt",
        "lat": 11.9404,
        "lon": 108.4583
    },
    {
        "farm_id": "FARM_MEKONG_02",
        "name": "Vựa lúa Đồng bằng Sông Cửu Long (Cần Thơ)",
        "lat": 10.0452,
        "lon": 105.7469
    },
    {
        "farm_id": "FARM_GIALAI_03",
        "name": "Nông trường Cà phê Tây Nguyên (Gia Lai)",
        "lat": 13.9833,
        "lon": 108.0000
    }
]

def fetch_real_agri_iot(lat, lon):
    """
    Gọi Open-Meteo API lấy dữ liệu ĐỘ ẨM ĐẤT & KHÍ HẬU THẬT 100%
    """
    url = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={lat}&longitude={lon}&"
        f"current=temperature_2m,relative_humidity_2m,soil_temperature_0cm,soil_moisture_0_to_1cm,precipitation&"
        f"timezone=Asia%2FBangkok"
    )
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=10) as response:
        res = json.loads(response.read().decode('utf-8'))
        return res.get("current", {})

def main():
    print("⏳ Đang kết nối tới Redpanda (localhost:9092)...")
    producer = KafkaProducer(
        bootstrap_servers=["localhost:9092"],
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        key_serializer=lambda k: k.encode("utf-8") if k else None
    )

    topic_name = "test-topic"
    print(f"🌾 BẮT ĐẦU KÉO DỮ LIỆU IOT THẬT TỪ 3 NÔNG TRƯỜNG VIỆT NAM -> BẮN VÀO TOPIC '{topic_name}'...")
    print("-----------------------------------------------------------------------------------------")

    try:
        round_count = 1
        while round_count <= 5: # Chạy 5 vòng lấy data thật
            print(f"\n📡 [VÒNG {round_count}] Đang lấy dữ liệu cảm biến thật từ API...")
            
            for farm in FARMS:
                real_data = fetch_real_agri_iot(farm["lat"], farm["lon"])
                
                payload = {
                    "farm_id": farm["farm_id"],
                    "farm_name": farm["name"],
                    "lat": farm["lat"],
                    "lon": farm["lon"],
                    "soil_moisture_pct": round(real_data.get("soil_moisture_0_to_1cm", 0.0) * 100, 1), # Đổi sang %
                    "soil_temp_c": real_data.get("soil_temperature_0cm"),
                    "air_temp_c": real_data.get("temperature_2m"),
                    "air_humidity_pct": real_data.get("relative_humidity_2m"),
                    "rain_mm": real_data.get("precipitation", 0.0),
                    "event_time": time.time(),
                    "source": "OPEN_METEO_LIVE_API"
                }

                # Bắn data thật vào Redpanda
                producer.send(topic_name, key=farm["farm_id"], value=payload)
                
                print(f"  🌱 {farm['farm_id']} ({farm['name']}):")
                print(f"     -> Độ ẩm đất thật: {payload['soil_moisture_pct']}% | Nhiệt độ đất: {payload['soil_temp_c']}°C | Nhiệt độ kk: {payload['air_temp_c']}°C")
                time.sleep(1)

            producer.flush()
            round_count += 1
            time.sleep(2)

        print("\n✅ ĐÃ HOÀN TẤT BẮN DỮ LIỆU IOT THẬT VÀO REDPANDA!")
        print("👉 Bây giờ bạn hãy mở thư mục: test_server/storage/kafka/test-topic-0/ để xem các bản tin thật được lưu trên ổ cứng!")

    except Exception as e:
        print(f"❌ Lỗi: {e}")
    finally:
        producer.close()

if __name__ == "__main__":
    main()
