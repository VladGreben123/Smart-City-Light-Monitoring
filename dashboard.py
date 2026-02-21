import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import joblib
import os
import shap
from xgboost import XGBClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, roc_auc_score, confusion_matrix

# Set page config
st.set_page_config(
    page_title="Street Light Predictive Maintenance Dashboard",
    page_icon="💡",
    layout="wide"
)

# Constants
DATA_PATH = 'data/synthetic_maintenance_data.csv'
MODEL_PATH = 'models/predictive_maintenance_model.joblib'

# Helper functions
@st.cache_data
def load_data():
    if os.path.exists(DATA_PATH):
        return pd.read_csv(DATA_PATH)
    return None

def save_data(df):
    os.makedirs('data', exist_ok=True)
    df.to_csv(DATA_PATH, index=False)

def train_new_model(df):
    X = df.drop('will_fail_in_7_days', axis=1)
    y = df['will_fail_in_7_days']
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    model = XGBClassifier(
        n_estimators=200,
        max_depth=6,
        learning_rate=0.05,
        eval_metric='logloss',
        early_stopping_rounds=10
    )
    
    model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)
    
    # Save model
    os.makedirs('models', exist_ok=True)
    joblib.dump(model, MODEL_PATH)
    
    # Evaluate
    preds = model.predict(X_test)
    preds_proba = model.predict_proba(X_test)[:, 1]
    
    report = classification_report(y_test, preds, output_dict=True)
    roc_auc = roc_auc_score(y_test, preds_proba)
    cm = confusion_matrix(y_test, preds)
    
    return model, report, roc_auc, cm, X_train.columns

# Sidebar
st.sidebar.title("Navigation")
page = st.sidebar.radio("Go to", ["Dashboard", "Data Explorer", "Model Training", "Interactive Prediction"])

# Main content
if page == "Dashboard":
    st.title("💡 Predictive Maintenance Overview")
    
    df = load_data()
    if df is not None:
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Total Lamps Monitored", f"{len(df):,}")
        
        with col2:
            failure_rate = (df['will_fail_in_7_days'].sum() / len(df)) * 100
            st.metric("Predicted Failure Rate (7 days)", f"{failure_rate:.1f}%")
            
        with col3:
            if os.path.exists(MODEL_PATH):
                st.metric("Model Status", "Active", delta="Ready")
            else:
                st.metric("Model Status", "Not Found", delta_color="inverse")
        
        st.subheader("Quick Stats")
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**Feature Distributions (Averages)**")
            st.dataframe(df.describe().loc['mean'].to_frame().T)
            
        with col2:
            st.write("**Failure Distribution**")
            fig, ax = plt.subplots(figsize=(6, 4))
            sns.countplot(x='will_fail_in_7_days', data=df, ax=ax, palette="viridis")
            ax.set_xticklabels(['Healthy', 'Will Fail'])
            st.pyplot(fig)
            
    else:
        st.warning("No data found. Please go to Data Explorer or run generation script.")

elif page == "Data Explorer":
    st.title("📊 Data Explorer")
    
    df = load_data()
    
    if df is not None:
        st.write(f"Dataset shape: {df.shape}")
        st.dataframe(df.head())
        
        st.subheader("Correlation Matrix")
        fig, ax = plt.subplots(figsize=(10, 8))
        sns.heatmap(df.corr(), annot=True, cmap='coolwarm', ax=ax)
        st.pyplot(fig)
        
        st.subheader("Feature Distributions")
        feature = st.selectbox("Select Feature", df.columns)
        
        fig, ax = plt.subplots(figsize=(10, 6))
        sns.histplot(data=df, x=feature, hue='will_fail_in_7_days', bins=30, kde=True, ax=ax)
        plt.title(f"Distribution of {feature} by Target")
        st.pyplot(fig)
        
    else:
        st.info("No data available. Generate synthetic data below.")
        if st.button("Generate Default Dataset (10,000 samples)"):
            # Import generation script logic here or run it
            try:
                from scripts.generation_syntetic import generate_data
                df = generate_data(n_samples=10000)
                save_data(df)
                st.success("Data generated and saved!")
                st.rerun()
            except ImportError:
                st.error("Could not import generation script. Make sure scripts/generation_syntetic.py exists.")

elif page == "Model Training":
    st.title("🤖 Model Training Center")
    
    df = load_data()
    
    if df is not None:
        st.write("Train a new XGBoost model on the current dataset.")
        
        if st.button("Train Model"):
            with st.spinner("Training model... This may take a moment."):
                # Import here to avoid circular dependency if possible, or ensure script is importable
                # Assuming generation_syntetic.py is in scripts/ and has train_model function
                # But we defined train_new_model above which does similar logic
                model, report, roc_auc, cm, feature_cols = train_new_model(df)
            
            st.success(f"Model trained successfully! ROC-AUC: {roc_auc:.3f}")
            
            # Save metrics to session state or file if needed
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("Classification Report")
                # Convert classification report dict to dataframe properly
                report_df = pd.DataFrame(report).transpose()
                st.dataframe(report_df.style.highlight_max(axis=0))
                
            with col2:
                st.subheader("Confusion Matrix")
                fig, ax = plt.subplots()
                sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', ax=ax)
                plt.xlabel('Predicted')
                plt.ylabel('Actual')
                st.pyplot(fig)
            
            st.subheader("Feature Importance")
            # Get feature importance
            importance = model.feature_importances_
            feature_names = feature_cols
            
            feat_imp = pd.DataFrame({'Feature': feature_names, 'Importance': importance})
            feat_imp = feat_imp.sort_values('Importance', ascending=False)
            
            fig, ax = plt.subplots(figsize=(10, 6))
            sns.barplot(x='Importance', y='Feature', data=feat_imp, ax=ax, palette='viridis')
            plt.title("XGBoost Feature Importance")
            st.pyplot(fig)
            
    else:
        st.warning("No data available to train model.")

elif page == "Interactive Prediction":
    st.title("🔮 Interactive Prediction Lab")
    
    if os.path.exists(MODEL_PATH):
        model = joblib.load(MODEL_PATH)
        
        st.subheader("Input Lamp Parameters")
        
        col1, col2 = st.columns(2)
        
        with col1:
            hours_active = st.number_input("Hours Active", min_value=0, max_value=20000, value=5000, step=100)
            on_off_cycles = st.number_input("On/Off Cycles", min_value=0, max_value=10000, value=2000, step=50)
            avg_temp_exposure = st.number_input("Avg Temp Exposure (°C)", min_value=-50.0, max_value=100.0, value=25.0, step=0.1)
            
        with col2:
            temp_fluctuations = st.number_input("Temp Fluctuations", min_value=0, max_value=100, value=10, step=1)
            voltage_spikes = st.number_input("Voltage Spikes", min_value=0, max_value=50, value=2, step=1)
            humidity_exposure = st.number_input("Humidity Exposure (%)", min_value=0.0, max_value=100.0, value=60.0, step=1.0)
            
        if st.button("Predict Failure Probability"):
            input_data = pd.DataFrame({
                'hours_active': [hours_active],
                'on_off_cycles': [on_off_cycles],
                'avg_temp_exposure': [avg_temp_exposure],
                'temp_fluctuations': [temp_fluctuations],
                'voltage_spikes': [voltage_spikes],
                'humidity_exposure': [humidity_exposure]
            })
            
            prob = model.predict_proba(input_data)[0][1]
            
            st.markdown("---")
            st.subheader("Prediction Result")
            
            col1, col2 = st.columns([1, 2])
            
            with col1:
                if prob > 0.7:
                    st.error(f"CRITICAL RISK")
                elif prob > 0.4:
                    st.warning(f"WARNING")
                else:
                    st.success(f"HEALTHY")
            
            with col2:
                st.metric("Failure Probability (7 days)", f"{prob:.2%}")
                st.progress(float(prob))
            
            # Simple explanation
            st.write("**Analysis:**")
            reasons = []
            if hours_active > 8000: reasons.append("- High operating hours")
            if voltage_spikes > 4: reasons.append("- Excessive voltage spikes detected")
            if temp_fluctuations > 30: reasons.append("- High thermal stress")
            
            if reasons:
                for r in reasons:
                    st.write(r)
            elif prob < 0.3:
                st.write("- All parameters within normal range")
                
    else:
        st.error("Model not found! Please train the model first.")
