import pandas as pd
import numpy as np
import os
from django.conf import settings


class DatasetLoader:
    """
    Load medication adherence dataset from Kaggle CSV file
    Dataset contains: Age, Gender, Medication_Type, Dosage_mg, Previous_Adherence,
    Education_Level, Income, Social_Support_Level, Condition_Severity,
    Comorbidities_Count, Healthcare_Access, Mental_Health_Status,
    Insurance_Coverage, Adherence (target)
    """
    
    def __init__(self, dataset_path=None):
        if dataset_path is None:
            # Default path to dataset
            self.dataset_path = os.path.join(settings.BASE_DIR, 'datasets', 'patient_adherence_dataset.csv')
        else:
            self.dataset_path = dataset_path
    
    def load_dataset(self):
        """
        Load dataset from CSV file
        """
        try:
            df = pd.read_csv(self.dataset_path)
            print(f"✅ Kaggle Dataset loaded: {len(df)} records")
            print(f"📊 Columns: {list(df.columns)}")
            return df
        except FileNotFoundError:
            print(f"❌ Dataset not found at: {self.dataset_path}")
            print("Please place 'patient_adherence_dataset.csv' in the datasets folder")
            return None
        except Exception as e:
            print(f"❌ Error loading dataset: {str(e)}")
            return None
    
    def get_dataset_info(self):
        """
        Get information about the dataset
        """
        df = self.load_dataset()
        
        if df is None:
            return None
        
        # Convert binary adherence to risk categories
        df = self._convert_adherence_to_risk(df)
        
        info = {
            'total_records': len(df),
            'features': list(df.columns),
            'adherence_distribution': df['Adherence'].value_counts().to_dict(),
            'risk_distribution': df['adherence_risk'].value_counts().to_dict() if 'adherence_risk' in df.columns else {},
            'age_range': {
                'min': int(df['Age'].min()),
                'max': int(df['Age'].max()),
                'mean': float(df['Age'].mean())
            },
            'gender_distribution': df['Gender'].value_counts().to_dict(),
            'medication_types': df['Medication_Type'].unique().tolist(),
            'severity_levels': df['Condition_Severity'].unique().tolist(),
            'features_description': {
                'Age': 'Patient age in years',
                'Gender': 'Male/Female/Other',
                'Medication_Type': 'Type of medication (TypeA/TypeB/TypeC)',
                'Dosage_mg': 'Medication dosage in mg',
                'Previous_Adherence': 'Previous adherence history (0/1)',
                'Education_Level': 'Patient education level',
                'Income': 'Annual income',
                'Social_Support_Level': 'Low/Medium/High',
                'Condition_Severity': 'Mild/Moderate/Severe',
                'Comorbidities_Count': 'Number of other conditions',
                'Healthcare_Access': 'Poor/Average/Good',
                'Mental_Health_Status': 'Poor/Moderate/Good',
                'Insurance_Coverage': 'Has insurance (0/1)',
                'Adherence': 'Target: Adherent (1) or Non-adherent (0)'
            }
        }
        
        return info
    
    def validate_dataset(self, df):
        """
        Validate that dataset has required columns
        """
        required_columns = [
            'Age', 'Gender', 'Medication_Type', 'Dosage_mg',
            'Previous_Adherence', 'Condition_Severity',
            'Comorbidities_Count', 'Adherence'
        ]
        
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            print(f"⚠️ Warning: Missing columns: {missing_columns}")
            return False
        
        print("✅ Dataset validation passed")
        return True
    
    def preprocess_dataset(self, df):
        """
        Preprocess Kaggle dataset for ML training
        """
        # Make a copy
        df = df.copy()
        
        # Handle missing values
        df = df.dropna()
        
        # Convert adherence_risk from binary to categories
        df = self._convert_adherence_to_risk(df)
        
        # Encode categorical variables
        
        # 1. Gender encoding
        gender_map = {'Male': 0, 'Female': 1, 'Other': 2}
        df['gender_encoded'] = df['Gender'].map(gender_map).fillna(2)
        
        # 2. Medication Type encoding
        med_type_map = {'TypeA': 0, 'TypeB': 1, 'TypeC': 2}
        df['medication_type_encoded'] = df['Medication_Type'].map(med_type_map).fillna(0)
        
        # 3. Education Level encoding
        education_map = {
            'High School': 0,
            'Graduate': 1,
            'Postgraduate': 2
        }
        df['education_encoded'] = df['Education_Level'].map(education_map).fillna(0)
        
        # 4. Social Support Level encoding
        support_map = {'Low': 0, 'Medium': 1, 'High': 2}
        df['social_support_encoded'] = df['Social_Support_Level'].map(support_map).fillna(1)
        
        # 5. Condition Severity encoding
        severity_map = {'Mild': 0, 'Moderate': 1, 'Severe': 2}
        df['severity_encoded'] = df['Condition_Severity'].map(severity_map).fillna(1)
        
        # 6. Healthcare Access encoding
        access_map = {'Poor': 0, 'Average': 1, 'Good': 2}
        df['healthcare_access_encoded'] = df['Healthcare_Access'].map(access_map).fillna(1)
        
        # 7. Mental Health Status encoding
        mental_map = {'Poor': 0, 'Moderate': 1, 'Good': 2}
        df['mental_health_encoded'] = df['Mental_Health_Status'].map(mental_map).fillna(1)
        
        # Normalize income (scale to 0-1)
        df['income_normalized'] = (df['Income'] - df['Income'].min()) / (df['Income'].max() - df['Income'].min())
        
        # Normalize dosage (scale to 0-1)
        df['dosage_normalized'] = (df['Dosage_mg'] - df['Dosage_mg'].min()) / (df['Dosage_mg'].max() - df['Dosage_mg'].min())
        
        print(f"✅ Dataset preprocessed: {len(df)} records after cleaning")
        
        return df
    
    def _convert_adherence_to_risk(self, df):
        """
        Convert binary adherence (0/1) to risk categories (low/medium/high)
        Based on multiple factors
        """
        df = df.copy()
        
        # Create risk score based on multiple factors
        risk_factors = []
        
        # Factor 1: Current non-adherence
        risk_factors.append((df['Adherence'] == 0).astype(int) * 0.3)
        
        # Factor 2: Previous non-adherence
        risk_factors.append((df['Previous_Adherence'] == 0).astype(int) * 0.2)
        
        # Factor 3: High number of comorbidities
        risk_factors.append((df['Comorbidities_Count'] >= 3).astype(int) * 0.15)
        
        # Factor 4: Severe condition
        severity_risk = df['Condition_Severity'].map({'Mild': 0, 'Moderate': 0.5, 'Severe': 1}).fillna(0.5)
        risk_factors.append(severity_risk * 0.15)
        
        # Factor 5: Poor healthcare access
        access_risk = df['Healthcare_Access'].map({'Good': 0, 'Average': 0.5, 'Poor': 1}).fillna(0.5)
        risk_factors.append(access_risk * 0.1)
        
        # Factor 6: Poor mental health
        mental_risk = df['Mental_Health_Status'].map({'Good': 0, 'Moderate': 0.5, 'Poor': 1}).fillna(0.5)
        risk_factors.append(mental_risk * 0.1)
        
        # Sum all risk factors
        risk_score = sum(risk_factors)
        
        # Categorize into low/medium/high
        df['adherence_risk'] = pd.cut(
            risk_score,
            bins=[-0.01, 0.33, 0.66, 1.01],
            labels=['low', 'medium', 'high']
        )
        
        return df
    
    def get_feature_importance_description(self):
        """
        Return description of features for model interpretation
        """
        return {
            'Age': 'Older patients may have memory issues affecting adherence',
            'Gender': 'Gender-based behavioral patterns',
            'Medication_Type': 'Different medications have different adherence patterns',
            'Dosage_mg': 'Higher dosages may affect adherence',
            'Previous_Adherence': 'Strong predictor of future behavior',
            'Education_Level': 'Better education often correlates with better adherence',
            'Income': 'Financial ability to afford medications',
            'Social_Support_Level': 'Family/friend support improves adherence',
            'Condition_Severity': 'Severe conditions may increase adherence awareness',
            'Comorbidities_Count': 'Multiple conditions complicate medication management',
            'Healthcare_Access': 'Ability to get medical care and refills',
            'Mental_Health_Status': 'Depression/anxiety affects medication adherence',
            'Insurance_Coverage': 'Insurance reduces financial barriers'
        }