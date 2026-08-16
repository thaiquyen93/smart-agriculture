# 05 — Lớp ML định lượng: Interface & Baseline

> Đây là lớp trả lời câu hỏi *"AI của các bạn là gì, ngoài việc gọi LLM?"* — và là thứ ngăn hệ thống bị chấm là rule-based.

---

## 1. Vì sao lớp này tồn tại riêng

BTC loại thẳng sản phẩm *"cảnh báo bằng điều kiện cố định (rule-based)"*. Nhưng một LLM gọi tool cũng chưa chắc thoát: nếu tool bên dưới chỉ là `if soil_moisture < 35: tưới` thì bản chất vẫn là rule-based, chỉ khoác thêm lớp ngôn ngữ.

Vì vậy tách riêng **mặt phẳng tri giác**: nơi con số được sinh ra bằng mô hình học được hoặc mô hình vật lý, chứ không phải hằng số cắm tay.

**Ranh giới cứng:**

| | Sinh con số | Diễn giải con số |
|---|---|---|
| **Lớp ML (file này)** | ✅ | ❌ |
| **LLM Agent** | ❌ | ✅ |

Agronomy Agent **không được** tính lượng nước. Nó gọi `estimate_water_demand()` rồi cân nhắc: có nên tưới lúc nắng gắt không, ưu tiên khu nào trước, dự báo cho phép hoãn tới chiều không. Đó là phần công thức không biểu diễn được — và là chỗ LLM thực sự có ích.

---

## 2. Chiến lược: interface trước, model sau

Nhánh `ai-fuzzy-branch` đang có người làm phần fuzzy/ML. Để không trùng việc mà cũng không bị chặn tiến độ:

1. `agent-core` định nghĩa **interface (ABC)** — hợp đồng cố định
2. `agent-core` tự có **baseline chạy được ngay** cho mỗi interface
3. Model từ `ai-fuzzy-branch` cắm vào **qua config**, không sửa dòng code agent nào

```
agent_core/models/
├── base.py                  # 4 ABC — hợp đồng
├── baseline/                # implementation của mình
│   ├── soil_forecaster.py
│   ├── water_demand.py
│   ├── pump_health.py
│   └── anomaly.py
├── external/                # adapter cho model của bạn khác
│   └── fuzzy_branch_adapter.py
└── registry.py              # đọc env → trả implementation
```

```env
MODEL_SOIL_FORECASTER=baseline    # baseline | fuzzy_branch
MODEL_WATER_DEMAND=baseline
MODEL_PUMP_HEALTH=baseline
MODEL_ANOMALY=baseline
```

Đổi một dòng env là thay model. Nếu model của bạn kia tốt hơn ở bộ eval → chuyển; nếu chưa xong → baseline vẫn chạy, demo không bị chặn.

---

## 3. Bốn interface

### 3.1 `SoilMoistureForecaster`

```python
class SoilMoistureForecaster(ABC):
    @abstractmethod
    def predict(
        self,
        device_id: str,
        horizons_minutes: list[int],
        history: pd.DataFrame,      # cột: ts, soil_moisture, temperature,
                                    # humidity, lux, flow_rate
    ) -> ForecastResult: ...

@dataclass
class ForecastResult:
    points: list[ForecastPoint]     # horizon_minutes, predicted_pct, ci_low, ci_high
    model_version: str              # ví dụ "gbr-0.2" | "physics-fallback"
    is_cold_start: bool
    feature_importances: dict[str, float]   # cho phần giải thích trên UI
```

**Baseline:**
- **Chính:** Gradient Boosting Regressor (`sklearn`), một model cho mỗi horizon.
  Feature: `soil_moisture` lag 1/5/15/30 phút · `soil_moisture` trend · `temperature`, `humidity`, `lux` hiện tại và trung bình 15 phút · `flow_rate` tích luỹ 30 phút (đã tưới bao nhiêu) · giờ trong ngày mã hoá sin/cos.
  Nhãn: `soil_moisture` tại `t + horizon`.
  Train: từ `telemetry_raw` trong SQLite; retrain nền mỗi 30 phút khi có ≥ 200 mẫu.
- **Fallback lạnh:** mô hình suy giảm vật lý — tốc độ bốc hơi tỉ lệ với ET0, cộng lượng nước bơm vào. Trả `is_cold_start=True`, `model_version="physics-fallback"`.

Fallback không phải giải pháp tình thế — 30 phút đầu chạy hệ thống *luôn* rơi vào trạng thái này, và giám khảo có thể vào đúng lúc đó. Nó phải cho kết quả hợp lý và **tự khai báo** mình là fallback.

`feature_importances` đưa lên UI trả lời được câu hỏi "vì sao mô hình dự báo vậy" — có ích khi phản biện.

---

### 3.2 `WaterDemandEstimator`

```python
class WaterDemandEstimator(ABC):
    @abstractmethod
    def estimate(
        self,
        zone: str,
        current_state: FarmSnapshot,
        crop_profile: CropProfile,
        horizon_hours: int = 6,
    ) -> WaterDemandResult: ...

@dataclass
class WaterDemandResult:
    volume_liters: float
    confidence_low: float
    confidence_high: float
    et0_mm_day: float
    method: str
    model_version: str
    breakdown: dict[str, float]   # đóng góp của từng thành phần
```

**Baseline — vật lý, không phải ngưỡng:**

1. **ET0 theo Hargreaves–Samani** (chọn vì chỉ cần nhiệt độ + bức xạ — đúng thứ 6 thiết bị có; Penman-Monteith cần tốc độ gió, mình không có):
   ```
   ET0 = 0.0023 × Ra × (Tmean + 17.8) × √(Tmax − Tmin)
   ```
   `Tmax`/`Tmin`/`Tmean` từ cửa sổ `WEATHER_01`; `Ra` (bức xạ ngoài khí quyển) suy từ `SUN_01.lux` hiệu chỉnh theo ngày trong năm.

2. **ETc** = ET0 × Kc (hệ số cây trồng, từ crop profile).

3. **Thiếu hụt ẩm:** `(target_pct − current_pct) / 100 × độ_sâu_rễ_mm × diện_tích_m²` → lít.

4. **Tổng:** thiếu hụt hiện tại + ETc dự kiến trong `horizon_hours`, chia hiệu suất tưới.

5. **Khoảng tin cậy:** lan truyền từ khoảng tin cậy của `SoilMoistureForecaster` + sai số ET0 (±15%).

`breakdown` trả về `{"deficit_liters": ..., "etc_liters": ..., "efficiency_loss_liters": ...}` để bản tin nói được *vì sao* ra con số đó.

> **Điểm phản biện:** đây không phải `deficit × 15.0` như code trên `main`. Đó là mô hình bốc-thoát hơi nước chuẩn FAO-56, dùng đúng cảm biến đề bài cho, có khoảng tin cậy và có bóc tách thành phần.

---

### 3.3 `PumpHealthDetector`

```python
class PumpHealthDetector(ABC):
    @abstractmethod
    def diagnose(self, device_id: str, history: pd.DataFrame) -> PumpHealthResult: ...

@dataclass
class PumpHealthResult:
    status: str          # OK | DEGRADED | FAULT | UNKNOWN
    efficiency_lpm_per_watt: float
    baseline_efficiency: float
    deviation_pct: float
    symptom: str         # NONE | LOW_FLOW_NORMAL_POWER
                         # | HIGH_POWER_NO_FLOW | INTERMITTENT
    model_version: str
```

**Baseline:**
- Chỉ số cốt lõi: **hiệu suất** `flow_rate / power` (L/min trên W), chỉ tính khi `power > 50W` (bơm đang chạy).
- Baseline hiệu suất: trung vị trượt 24 giờ **của chính bơm đó** (tự thích nghi, không phải hằng số cắm tay).
- Lệch bằng **robust z-score** (MAD), không dùng độ lệch chuẩn — bền với ngoại lai.
  `|z| > 3.5` → `FAULT` · `2.0 < |z| ≤ 3.5` → `DEGRADED`
- Phân loại triệu chứng: `flow` thấp + `power` bình thường → nghi **tắc lọc**; `power` cao + `flow` ≈ 0 → nghi **chạy khô** (nguy hiểm cho bơm).

> Điểm mấu chốt: chẩn đoán trên **tỉ số** so với đường nền học được của chính thiết bị, không phải ngưỡng tuyệt đối trên từng chỉ số. Một cái bơm ở `600W, 8 L/min` có thể bình thường hoặc hỏng — chỉ hiệu suất so với lịch sử của nó mới trả lời được.

---

### 3.4 `AnomalyDetector`

```python
class AnomalyDetector(ABC):
    @abstractmethod
    def detect(self, zone: str, windows: pd.DataFrame) -> list[Anomaly]: ...

@dataclass
class Anomaly:
    anomaly_type: str
    device_id: str
    score_0_1: float
    detected_at: datetime
    model_version: str
    contributing_features: list[str]
```

**Baseline:** Isolation Forest đa biến (`sklearn`) trên vector đặc trưng ghép từ cửa sổ `topic_p` của cả 6 thiết bị (`soil_moisture_avg`, `temperature_avg` ×2, `humidity_avg`, `flow_rate_avg`, `power_avg`, `ph_avg`, `level_avg`, `lux_avg` + các `_trend` tương ứng).

- `contamination=0.02`, fit lại mỗi 30 phút trên cửa sổ trượt 6 giờ
- `score_0_1` chuẩn hoá từ `decision_function`
- `contributing_features`: xấp xỉ bằng độ lệch từng feature so với trung vị — **luôn phải có**, vì một điểm bất thường không nói được nó bất thường ở đâu thì vô dụng với người vận hành

**Bổ sung — kiểm tra nhất quán liên thiết bị** (thứ mô hình đơn biến không bắt được):
- `PUMP_01.flow_rate > 0` nhưng `SOIL_01.soil_moisture` không tăng sau 10 phút → nghi vỡ ống / cảm biến đất hỏng
- `TANK_01.level` giảm nhưng `PUMP_01.flow_rate ≈ 0` → nghi rò rỉ
- `SUN_01.lux` cao nhưng `WEATHER_01.temperature` giảm mạnh → nghi cảm biến lệch chuẩn

Ba luật này *là* rule-based — và chúng được giữ có chủ đích, dán nhãn `cross_device_consistency`, **không** phải nguồn quyết định chính. Chúng bắt lỗi hệ thống mà mô hình thống kê đơn thiết bị không thấy. Thành thật về điều này tốt hơn là giả vờ mọi thứ đều là ML.

---

## 4. Chống cold-start

Mọi model đều có thể ở trạng thái chưa sẵn sàng. Quy tắc chung:

| Tình huống | Hành vi |
|---|---|
| Chưa đủ dữ liệu train | Dùng fallback vật lý/heuristic, đặt `is_cold_start=True`, `model_version` có hậu tố `-fallback` |
| Thiếu thiết bị đầu vào | Trả `error_code: INSUFFICIENT_DATA` kèm ghi rõ thiếu thiết bị nào |
| Model ném exception | Log, trả `UNKNOWN`, **không** làm sập phiên agent |

Và quan trọng nhất: **`model_version` luôn được truyền lên tới UI**. Người xem phải phân biệt được kết luận đến từ mô hình đã học hay từ fallback. Che giấu điều này chính là kiểu "kết luận quá mức khi thiếu dữ liệu" mà BTC nói sẽ trừ điểm.

---

## 5. Cắm model từ `ai-fuzzy-branch`

Chủ nhánh đó chỉ cần:

1. Implement một trong 4 ABC ở `base.py`
2. Đặt file vào `agent_core/models/external/`
3. Đăng ký trong `registry.py`
4. Đổi biến env tương ứng

Không cần biết gì về agent, prompt, hay tool. Interface là toàn bộ bề mặt tiếp xúc.

**Nếu fuzzy logic phù hợp ở đâu:** hợp lý nhất là làm lớp *diễn giải* trên `WaterDemandEstimator` — chuyển con số lít thành mức ưu tiên mờ (`hơi khô` / `khô` / `rất khô`), thay cho ngưỡng cứng. Fuzzy mạnh ở việc mô hình hoá ranh giới mờ giữa các nhãn; nó không thay thế được mô hình ET0.

---

## 6. Phụ thuộc thêm

```
scikit-learn>=1.4.0     # GradientBoosting, IsolationForest
pandas>=2.2.0           # xử lý chuỗi thời gian
numpy>=1.26.0
```

`scikit-learn` và `numpy` đã có sẵn trong `services/ai-agent/requirements.txt` — không phải phụ thuộc mới với dự án.
