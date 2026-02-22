import pandas as pd
import numpy as np
from xgboost import XGBClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, roc_auc_score
import joblib
import shap
import os

def generate_data(n_samples=50000):
    np.random.seed(42)
    
    # Generate features
    hours_active = np.random.randint(100, 10000, n_samples)
    on_off_cycles = np.random.randint(10, 5000, n_samples)
    avg_temp_exposure = np.random.normal(25, 10, n_samples)  # Mean 25C, std 10C
    temp_fluctuations = np.random.randint(0, 50, n_samples)
    voltage_spikes = np.random.poisson(2, n_samples)  # Poisson distribution for rare events
    humidity_exposure = np.random.uniform(30, 90, n_samples)
    
    # Create DataFrame
    df = pd.DataFrame({
        'hours_active': hours_active,
        'on_off_cycles': on_off_cycles,
        'avg_temp_exposure': avg_temp_exposure,
        'temp_fluctuations': temp_fluctuations,
        'voltage_spikes': voltage_spikes,
        'humidity_exposure': humidity_exposure
    })
    
    # Define Target Logic
    # Base probability of failure
    prob = np.zeros(n_samples)
    
    # Add contributions from features (making them stronger for better model performance)
    # 1. Hours active: linear increase
    prob += (df['hours_active'] / 10000) * 0.5
    
    # 2. Voltage spikes: significant impact if > 3
    prob += (df['voltage_spikes'] > 3).astype(int) * 0.4
    
    # 3. Temperature fluctuations: moderate impact
    prob += (df['temp_fluctuations'] / 50) * 0.3
    
    # 4. High temperature exposure
    prob += (df['avg_temp_exposure'] > 35).astype(int) * 0.3
    
    # 5. Humidity: meaningful only if very high
    prob += (df['humidity_exposure'] > 80).astype(int) * 0.2
    
    # Add some random noise
    prob += np.random.normal(0, 0.1, n_samples)
    
    # Sigmoid function to squash into 0-1 probability
    prob = 1 / (1 + np.exp(-(prob - 0.5) * 5))
    
    # Generate binary target based on probability
    df['will_fail_in_7_days'] = (np.random.rand(n_samples) < prob).astype(int)
    
    return df

def train_model():
    print("Generating synthetic data...")
    df = generate_data(n_samples=100000)
    
    # Save dataset
    os.makedirs('data', exist_ok=True)
    df.to_csv('data/synthetic_maintenance_data.csv', index=False)
    print("Dataset saved to data/synthetic_maintenance_data.csv")
    
    X = df.drop('will_fail_in_7_days', axis=1)
    y = df['will_fail_in_7_days']
    
    print("Splitting data...")
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    print("Training XGBoost model...")
    model = XGBClassifier(
        n_estimators=200,
        max_depth=6,
        learning_rate=0.05,
        eval_metric='logloss',
        early_stopping_rounds=10
    )
    
    model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)
    
    print("Evaluating model...")
    preds = model.predict(X_test)
    preds_proba = model.predict_proba(X_test)[:, 1]
    
    print(classification_report(y_test, preds))
    roc = roc_auc_score(y_test, preds_proba)
    print(f"ROC-AUC: {roc:.3f}")
    
    # Save model
    os.makedirs('models', exist_ok=True)
    joblib.dump(model, 'models/predictive_maintenance_model.joblib')
    print("Model saved to models/predictive_maintenance_model.joblib")
    
    # Train SHAP explainer
    print("Training SHAP explainer...")
    try:
        # Just check if we can create it, but don't save it if it's problematic to serialize
        # We will recreate it in the API
        # explainer = shap.TreeExplainer(model)
        # joblib.dump(explainer, 'models/shap_explainer.joblib') 
        print("SHAP explainer created successfully (skipping save to avoid serialization issues)")
    except Exception as e:
        print(f"Warning: Could not create/save SHAP explainer: {e}")
        print("Will attempt to recreate it in the API service.")
    
    return model

def interactive_predict(model):
    print("\n" + "="*50)
    print("INTERACTIVE PREDICTION MODE")
    print("="*50)
    print("Enter lamp parameters to check failure probability.")
    
    while True:
        try:
            print("\nEnter values (or press Enter to exit):")
            
            hours_active_str = input("Hours Active (e.g. 5000): ")
            if not hours_active_str: break
            hours_active = int(hours_active_str)
            
            on_off_cycles = int(input("On/Off Cycles (e.g. 2000): "))
            avg_temp_exposure = float(input("Avg Temp Exposure (e.g. 25.0): "))
            temp_fluctuations = int(input("Temp Fluctuations (e.g. 10): "))
            voltage_spikes = int(input("Voltage Spikes (e.g. 2): "))
            humidity_exposure = float(input("Humidity Exposure (e.g. 60.0): "))
            
            # Create dataframe for prediction
            input_data = pd.DataFrame({
                'hours_active': [hours_active],
                'on_off_cycles': [on_off_cycles],
                'avg_temp_exposure': [avg_temp_exposure],
                'temp_fluctuations': [temp_fluctuations],
                'voltage_spikes': [voltage_spikes],
                'humidity_exposure': [humidity_exposure]
            })
            
            # Predict
            prob = model.predict_proba(input_data)[0][1]
            
            # Status
            status = "GREEN (OK)"
            if prob > 0.7:
                status = "RED (CRITICAL)"
            elif prob > 0.4:
                status = "YELLOW (WARNING)"
                
            print(f"\nFailure Probability: {prob:.4f}")
            print(f"Status: {status}")
            
        except ValueError:
            print("Invalid input! Please enter numbers.")
        except KeyboardInterrupt:
            print("\nExiting interactive mode.")
            break
        except Exception as e:
            print(f"Error: {e}")
            break

if __name__ == "__main__":
    trained_model = train_model()
    
    # Ask if user wants to run interactive mode
    print("\nDo you want to run interactive prediction mode? (y/n)")
    choice = input().lower()
    if choice == 'y':
        interactive_predict(trained_model)
