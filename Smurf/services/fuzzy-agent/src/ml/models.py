import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
import os

class SensorLSTM(nn.Module):
    def __init__(self, input_size=1, hidden_layer_size=64, num_layers=2, output_size=1):
        super(SensorLSTM, self).__init__()
        self.hidden_layer_size = hidden_layer_size
        self.num_layers = num_layers
        
        # LSTM layer
        self.lstm = nn.LSTM(input_size, hidden_layer_size, num_layers, batch_first=True, dropout=0.2)
        
        # Fully connected layer
        self.linear = nn.Linear(hidden_layer_size, output_size)

    def forward(self, x):
        # x shape: (batch_size, seq_len, input_size)
        
        # LSTM output
        lstm_out, _ = self.lstm(x)
        
        # We only want the output of the last time step
        last_time_step_out = lstm_out[:, -1, :]
        
        # Fully connected layer to get final prediction
        predictions = self.linear(last_time_step_out)
        return predictions


class SensorPredictorService:
    def __init__(self, model_save_dir="models/"):
        self.model_save_dir = model_save_dir
        os.makedirs(self.model_save_dir, exist_ok=True)
        
        # 8 data fields to predict
        self.sensor_fields = [
            "soil_moisture", "temperature", "humidity", 
            "flow_rate", "power", "ph", "level", "lux"
        ]
        
        # Initialize 8 separate models
        self.models = {field: SensorLSTM() for field in self.sensor_fields}
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        
        for field in self.sensor_fields:
            self.models[field].to(self.device)
            self._load_model(field)

    def _get_model_path(self, field):
        return os.path.join(self.model_save_dir, f"lstm_{field}.pth")

    def _load_model(self, field):
        """Loads model weights if they exist."""
        path = self._get_model_path(field)
        if os.path.exists(path):
            try:
                self.models[field].load_state_dict(torch.load(path, map_location=self.device))
                print(f"Loaded model for {field}")
            except Exception as e:
                print(f"Could not load model for {field}: {e}")

    def save_model(self, field):
        """Saves model weights."""
        path = self._get_model_path(field)
        torch.save(self.models[field].state_dict(), path)
        print(f"Saved model for {field} to {path}")

    def predict(self, field, current_10_values):
        """
        Predicts the value 1 hour later (10 steps ahead) based on 10 current values.
        :param field: String, the name of the sensor field.
        :param current_10_values: List of 10 float values (collected every 6 mins).
        :return: Float, the predicted value 1 hour later.
        """
        if field not in self.models:
            raise ValueError(f"Field {field} is not supported.")
        
        if len(current_10_values) != 10:
            raise ValueError("Exactly 10 values are required for prediction.")
            
        model = self.models[field]
        model.eval()
        
        # Convert to tensor: shape (batch_size=1, seq_len=10, input_size=1)
        input_tensor = torch.tensor(current_10_values, dtype=torch.float32).view(1, 10, 1).to(self.device)
        
        with torch.no_grad():
            prediction = model(input_tensor)
            
        return prediction.item()

    def train_model(self, field, train_data, epochs=100, learning_rate=0.001):
        """
        Trains the LSTM model for a specific field.
        :param field: String, the name of the sensor field.
        :param train_data: List of tuples (sequence_of_10, target_value_1_hour_later)
        """
        if field not in self.models:
            raise ValueError(f"Field {field} is not supported.")
            
        model = self.models[field]
        model.train()
        
        criterion = nn.MSELoss()
        optimizer = optim.Adam(model.parameters(), lr=learning_rate)
        
        # Prepare batches
        X = torch.tensor([item[0] for item in train_data], dtype=torch.float32).view(-1, 10, 1).to(self.device)
        y = torch.tensor([item[1] for item in train_data], dtype=torch.float32).view(-1, 1).to(self.device)
        
        for epoch in range(epochs):
            optimizer.zero_grad()
            outputs = model(X)
            loss = criterion(outputs, y)
            loss.backward()
            optimizer.step()
            
            if (epoch + 1) % 10 == 0:
                print(f"[{field}] Epoch {epoch+1}/{epochs}, Loss: {loss.item():.4f}")
                
        self.save_model(field)


# --- DUMMY DATA TESTING (Can be run locally to verify) ---
if __name__ == "__main__":
    print("Testing SensorPredictorService architecture...")
    service = SensorPredictorService()
    
    # Generate some dummy data to simulate training (sine wave-like data)
    # 10 input values -> predict 1 output value (10 steps ahead)
    print("\n--- Training dummy model for 'temperature' ---")
    dummy_train_data = []
    for _ in range(100):
        # random sequence
        seq = np.random.rand(10).tolist()
        # dummy target: sum of seq + some noise
        target = sum(seq) / 10.0 + 0.5 
        dummy_train_data.append((seq, target))
        
    service.train_model("temperature", dummy_train_data, epochs=50)
    
    # Test Prediction
    print("\n--- Testing Prediction ---")
    sample_input = [25.1, 25.2, 25.3, 25.4, 25.5, 25.6, 25.7, 25.8, 25.9, 26.0]
    predicted_val = service.predict("temperature", sample_input)
    print(f"Input past 10 values (6 min intervals): {sample_input}")
    print(f"Predicted 'temperature' value 1 hour later: {predicted_val:.4f}")
