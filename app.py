import pandas as pd
import numpy as np
import joblib
import shap
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
import os

app = FastAPI(title="Predictive Maintenance API", description="API for predicting street light failure probability")

# Global variables
model = None
explainer = None

@app.on_event("startup")
async def load_model():
    global model, explainer
    model_path = 'models/predictive_maintenance_model.joblib'
    
    if os.path.exists(model_path):
        try:
            model = joblib.load(model_path)
            print(f"Model loaded from {model_path}")
            
            # Initialize SHAP explainer
            try:
                # Use the underlying booster to avoid sklearn wrapper issues with SHAP
                booster = model.get_booster()
                # Ensure base_score is float (fix for potential version mismatch)
                # This is a common fix for "could not convert string to float" error in SHAP with XGBoost
                # However, modifying it might affect prediction if not careful. 
                # TreeExplainer usually handles boosters well.
                booster.set_param({"base_score": 0.5})
                
                explainer = shap.TreeExplainer(booster)
                print("SHAP explainer initialized successfully.")
            except Exception as e:
                print(f"Warning: Error initializing SHAP explainer: {e}")
                print("SHAP explanations will not be available.")
                
        except Exception as e:
            print(f"Error loading model: {e}")
    else:
        print(f"Model file not found at {model_path}")

class LampFeatures(BaseModel):
    hours_active: int
    on_off_cycles: int
    avg_temp_exposure: float
    temp_fluctuations: int
    voltage_spikes: int
    humidity_exposure: float

@app.get("/")
def read_root():
    return {
        "status": "online", 
        "service": "Predictive Maintenance API",
        "model_loaded": model is not None,
        "shap_enabled": explainer is not None
    }

@app.post("/predict")
def predict_failure(features: LampFeatures):
    if not model:
        raise HTTPException(status_code=503, detail="Model not loaded")
    
    # Create DataFrame from input
    data = pd.DataFrame([features.model_dump()])
    
    # Ensure column order matches training
    expected_cols = ['hours_active', 'on_off_cycles', 'avg_temp_exposure', 'temp_fluctuations', 'voltage_spikes', 'humidity_exposure']
    data = data[expected_cols]
    
    # Predict probability
    # probability of class 1 (failure)
    try:
        prob = model.predict_proba(data)[0][1]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prediction error: {e}")
    
    # Get SHAP values
    shap_values_dict = {}
    if explainer:
        try:
            # shap_values for binary classification with TreeExplainer on booster 
            # usually returns raw margin values (log odds)
            shap_values = explainer.shap_values(data)
            
            # If it's a list (multiclass), take the relevant class. For binary XGBoost booster, it's usually an array.
            if isinstance(shap_values, list):
                sv = shap_values[0] # Should be checked, but for binary booster usually it's direct array
            else:
                sv = shap_values
                
            # sv is (n_samples, n_features) -> (1, 6)
            if len(sv.shape) == 2:
                sv = sv[0]
            
            # Map feature names to shap values
            feature_names = data.columns
            
            # Calculate contribution percentage (simplified for demo)
            # We take absolute values to show magnitude of impact
            abs_shap = np.abs(sv)
            total_impact = np.sum(abs_shap)
            
            if total_impact > 0:
                for i, name in enumerate(feature_names):
                    # Contribution to the deviation from base value
                    contribution = (abs_shap[i] / total_impact) * 100
                    
                    # Add direction (+/-) to show if it increases or decreases risk
                    # Actually, for the UI "Reason", we usually care about what INCREASES risk.
                    # So let's filter for positive SHAP values (increasing risk) if prob is high
                    # Or just show magnitude.
                    
                    # Let's show magnitude and direction string
                    impact_type = "increase" if sv[i] > 0 else "decrease"
                    
                    if sv[i] > 0: # Only show factors contributing to failure
                        shap_values_dict[name] = {
                            "contribution_percent": round(contribution, 1),
                            "impact": impact_type,
                            "value": float(sv[i])
                        }
            
            # Sort by contribution
            shap_values_dict = dict(sorted(shap_values_dict.items(), key=lambda item: item[1]['contribution_percent'], reverse=True))
            
        except Exception as e:
            print(f"SHAP calculation error: {e}")
            pass

    # Determine status color
    status_color = "green"
    if prob > 0.7:
        status_color = "red"
    elif prob > 0.4:
        status_color = "yellow"
        
    return {
        "failure_probability": round(float(prob), 4),
        "status_color": status_color,
        "risk_level": "Critical" if prob > 0.7 else ("Warning" if prob > 0.4 else "Normal"),
        "key_factors": shap_values_dict
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
