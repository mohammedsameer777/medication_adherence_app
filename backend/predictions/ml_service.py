import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split, StratifiedKFold, cross_val_score
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier, VotingClassifier
from sklearn.svm import SVC
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score,
    f1_score, confusion_matrix, classification_report
)
import xgboost as xgb
import pickle
import os
from django.conf import settings
from .data_loader import DatasetLoader
import pytesseract

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


class AdherencePredictor:
    """
    Machine Learning service for medication adherence prediction.
    Improvements in this version:
      - Fixed adherence_score bug (was always 1.0, now uses low-risk probability)
      - StandardScaler added for better accuracy
      - Tuned hyperparameters for RF, GB, XGBoost
      - Voting Ensemble from top 3 models for best accuracy
      - 5-fold cross-validation during training
    """

    def __init__(self):
        self.models = {}
        self.label_encoders = {}
        self.scaler = None
        self.best_model = None
        self.best_model_name = None
        self.feature_names = []
        self.feature_importances = {}
        self.model_path = os.path.join(settings.BASE_DIR, 'ml_models')
        self.dataset_loader = DatasetLoader()

        if not os.path.exists(self.model_path):
            os.makedirs(self.model_path)

    # ─────────────────────────────────────────────────────────────────────────
    # DATASET
    # ─────────────────────────────────────────────────────────────────────────

    def load_dataset(self):
        df = self.dataset_loader.load_dataset()
        if df is None:
            raise Exception("Failed to load Kaggle dataset")
        if not self.dataset_loader.validate_dataset(df):
            raise Exception("Dataset validation failed")
        df = self.dataset_loader.preprocess_dataset(df)
        return df

    # ─────────────────────────────────────────────────────────────────────────
    # FEATURE SELECTION
    # ─────────────────────────────────────────────────────────────────────────

    def prepare_features(self, df):
        """
        1. Run Random Forest on ALL 13 features to get importance scores
        2. Select top 7 most important features
        3. Scale with StandardScaler (improves LR and SVM accuracy)
        """
        all_features = [
            'Age',
            'gender_encoded',
            'medication_type_encoded',
            'dosage_normalized',
            'Previous_Adherence',
            'education_encoded',
            'income_normalized',
            'social_support_encoded',
            'severity_encoded',
            'Comorbidities_Count',
            'healthcare_access_encoded',
            'mental_health_encoded',
            'Insurance_Coverage'
        ]

        X_all = df[all_features]

        if 'adherence_risk' not in self.label_encoders:
            self.label_encoders['adherence_risk'] = LabelEncoder()
            y = self.label_encoders['adherence_risk'].fit_transform(df['adherence_risk'])
        else:
            y = self.label_encoders['adherence_risk'].transform(df['adherence_risk'])

        # Feature selection via Random Forest
        print("\n🔍 Running feature selection using Random Forest...")
        selector_rf = RandomForestClassifier(
            n_estimators=200,
            max_depth=10,
            random_state=42,
            n_jobs=-1,
            class_weight='balanced'
        )
        selector_rf.fit(X_all, y)

        importances = dict(zip(all_features, selector_rf.feature_importances_))
        sorted_features = sorted(importances, key=importances.get, reverse=True)

        print("\n📊 Feature Importance Rankings (all 13 features):")
        for i, feat in enumerate(sorted_features, 1):
            marker = "✅" if i <= 7 else "  "
            print(f"   {marker} {i:2}. {feat:<35} {importances[feat]:.4f}")

        self.feature_names = sorted_features[:7]
        self.feature_importances = importances

        print(f"\n✅ Selected top 7 features: {self.feature_names}")

        # Scale selected features
        X_selected = df[self.feature_names].values
        self.scaler = StandardScaler()
        X_scaled = self.scaler.fit_transform(X_selected)

        return X_scaled, y

    # ─────────────────────────────────────────────────────────────────────────
    # TRAINING
    # ─────────────────────────────────────────────────────────────────────────

    def train_models(self):
        print("\n" + "=" * 70)
        print("TRAINING MEDICATION ADHERENCE PREDICTION MODELS")
        print("Using Real Kaggle Dataset: patient_adherence_dataset.csv")
        print("=" * 70)

        print("\n📂 Loading Kaggle dataset...")
        df = self.load_dataset()

        print(f"\n✅ Dataset loaded: {len(df)} records")

        risk_dist = df['adherence_risk'].value_counts()
        print(f"\n   Risk distribution:")
        for risk, count in risk_dist.items():
            print(f"      {risk}: {count} ({count / len(df) * 100:.1f}%)")

        print("\n🔧 Preparing & selecting features...")
        X, y = self.prepare_features(df)

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )

        print(f"\n   Training samples: {len(X_train)}")
        print(f"   Testing samples:  {len(X_test)}")

        # Improved model hyperparameters
        models_to_train = {
            'Logistic Regression': LogisticRegression(
                max_iter=2000,
                random_state=42,
                class_weight='balanced',
                C=0.5,
                solver='lbfgs',
            ),
            'Random Forest': RandomForestClassifier(
                n_estimators=500,
                max_depth=12,
                min_samples_split=4,
                min_samples_leaf=2,
                max_features='sqrt',
                random_state=42,
                class_weight='balanced',
                n_jobs=-1,
                bootstrap=True,
                oob_score=True,
            ),
            'Gradient Boosting': GradientBoostingClassifier(
                n_estimators=300,
                learning_rate=0.05,
                max_depth=5,
                min_samples_split=4,
                subsample=0.8,
                random_state=42,
            ),
            'XGBoost': xgb.XGBClassifier(
                n_estimators=300,
                learning_rate=0.05,
                max_depth=6,
                subsample=0.8,
                colsample_bytree=0.8,
                random_state=42,
                use_label_encoder=False,
                eval_metric='mlogloss',
                n_jobs=-1,
            ),
        }

        results = []
        cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

        print("\n" + "=" * 70)
        print("MODEL TRAINING RESULTS")
        print("=" * 70)

        for name, model in models_to_train.items():
            print(f"\n🤖 Training {name}...")

            model.fit(X_train, y_train)
            y_pred = model.predict(X_test)

            accuracy  = accuracy_score(y_test, y_pred)
            precision = precision_score(y_test, y_pred, average='weighted', zero_division=0)
            recall    = recall_score(y_test, y_pred, average='weighted', zero_division=0)
            f1        = f1_score(y_test, y_pred, average='weighted', zero_division=0)
            cm        = confusion_matrix(y_test, y_pred)

            cv_scores = cross_val_score(model, X, y, cv=cv, scoring='f1_weighted', n_jobs=-1)

            print(f"   ✅ Accuracy:        {accuracy * 100:.2f}%")
            print(f"   ✅ Precision:       {precision * 100:.2f}%")
            print(f"   ✅ Recall:          {recall * 100:.2f}%")
            print(f"   ✅ F1 Score:        {f1 * 100:.2f}%")
            print(f"   ✅ CV F1 (5-fold):  {cv_scores.mean() * 100:.2f}% ± {cv_scores.std() * 100:.2f}%")

            if name == 'Random Forest' and hasattr(model, 'oob_score_'):
                print(f"   ✅ OOB Score:       {model.oob_score_ * 100:.2f}%")

            labels = self.label_encoders['adherence_risk'].classes_
            report = classification_report(y_test, y_pred, target_names=labels, zero_division=0)
            print(f"\n   Classification Report:")
            print("   " + report.replace('\n', '\n   '))

            if hasattr(model, 'feature_importances_'):
                print(f"   Top 5 Important Features:")
                imp = model.feature_importances_
                idx = np.argsort(imp)[::-1][:5]
                for i, j in enumerate(idx, 1):
                    print(f"      {i}. {self.feature_names[j]}: {imp[j]:.4f}")

            results.append({
                'model_name': name,
                'model': model,
                'accuracy': accuracy,
                'precision': precision,
                'recall': recall,
                'f1_score': f1,
                'cv_f1_mean': cv_scores.mean(),
                'confusion_matrix': cm
            })
            self.models[name] = model

        # Build Voting Ensemble from top 3 models
        # Build Voting Ensemble — sklearn models ONLY (XGBoost excluded)
        print("\n🔗 Building Voting Ensemble (sklearn models only)...")
        sklearn_only = [r for r in results if r['model_name'] != 'XGBoost']
        top3 = sorted(sklearn_only, key=lambda x: x['cv_f1_mean'], reverse=True)[:3]
        print(f"   Using: {[r['model_name'] for r in top3]}")
        estimators = [(r['model_name'].replace(' ', '_'), r['model']) for r in top3]
        voting_clf = VotingClassifier(estimators=estimators, voting='soft', n_jobs=-1)
        voting_clf.fit(X_train, y_train)
        y_pred_v = voting_clf.predict(X_test)

        v_acc = accuracy_score(y_test, y_pred_v)
        v_f1  = f1_score(y_test, y_pred_v, average='weighted', zero_division=0)
        v_pre = precision_score(y_test, y_pred_v, average='weighted', zero_division=0)
        v_rec = recall_score(y_test, y_pred_v, average='weighted', zero_division=0)

        print(f"   ✅ Ensemble Accuracy: {v_acc * 100:.2f}%")
        print(f"   ✅ Ensemble F1:       {v_f1 * 100:.2f}%")

        results.append({
            'model_name': 'Voting Ensemble',
            'model': voting_clf,
            'accuracy': v_acc,
            'precision': v_pre,
            'recall': v_rec,
            'f1_score': v_f1,
            'cv_f1_mean': v_f1,
            'confusion_matrix': confusion_matrix(y_test, y_pred_v)
        })
        self.models['Voting Ensemble'] = voting_clf

        # Select best model by F1
        best_result = max(results, key=lambda x: x['f1_score'])
        self.best_model      = best_result['model']
        self.best_model_name = best_result['model_name']

        print("\n" + "=" * 70)
        print("🏆 BEST MODEL SELECTED")
        print("=" * 70)
        print(f"   Model:     {self.best_model_name}")
        print(f"   Accuracy:  {best_result['accuracy'] * 100:.2f}%")
        print(f"   Precision: {best_result['precision'] * 100:.2f}%")
        print(f"   Recall:    {best_result['recall'] * 100:.2f}%")
        print(f"   F1 Score:  {best_result['f1_score'] * 100:.2f}%")
        print("=" * 70 + "\n")

        self.save_model(self.best_model, self.best_model_name)
        self._save_dataset_info(df)

        return results

    # ─────────────────────────────────────────────────────────────────────────
    # SAVE / LOAD
    # ─────────────────────────────────────────────────────────────────────────

    def save_model(self, model, model_name):
        filename = f"{model_name.replace(' ', '_').lower()}_model.pkl"
        filepath = os.path.join(self.model_path, filename)

        with open(filepath, 'wb') as f:
            pickle.dump(model, f)

        with open(os.path.join(self.model_path, 'label_encoders.pkl'), 'wb') as f:
            pickle.dump(self.label_encoders, f)

        with open(os.path.join(self.model_path, 'feature_names.pkl'), 'wb') as f:
            pickle.dump(self.feature_names, f)

        with open(os.path.join(self.model_path, 'feature_importances.pkl'), 'wb') as f:
            pickle.dump(self.feature_importances, f)

        with open(os.path.join(self.model_path, 'scaler.pkl'), 'wb') as f:
            pickle.dump(self.scaler, f)

        print(f"✅ Model saved: {filepath}")

    def load_model(self, model_name=None):
        if model_name is None:
            model_files = [f for f in os.listdir(self.model_path)
                           if f.endswith('_model.pkl')]
            if not model_files:
                raise FileNotFoundError(
                    "No trained models found. Please train models first.")
            filename = model_files[0]
            model_name = filename.replace('_model.pkl', '').replace('_', ' ').title()
        else:
            filename = f"{model_name.replace(' ', '_').lower()}_model.pkl"

        filepath = os.path.join(self.model_path, filename)
        with open(filepath, 'rb') as f:
            model = pickle.load(f)

        with open(os.path.join(self.model_path, 'label_encoders.pkl'), 'rb') as f:
            self.label_encoders = pickle.load(f)

        with open(os.path.join(self.model_path, 'feature_names.pkl'), 'rb') as f:
            self.feature_names = pickle.load(f)

        imp_path = os.path.join(self.model_path, 'feature_importances.pkl')
        if os.path.exists(imp_path):
            with open(imp_path, 'rb') as f:
                self.feature_importances = pickle.load(f)

        scaler_path = os.path.join(self.model_path, 'scaler.pkl')
        if os.path.exists(scaler_path):
            with open(scaler_path, 'rb') as f:
                self.scaler = pickle.load(f)

        self.best_model      = model
        self.best_model_name = model_name

        print(f"✅ Model loaded: {filepath}")
        print(f"✅ Using selected features: {self.feature_names}")
        return model

    # ─────────────────────────────────────────────────────────────────────────
    # PREDICTION  (adherence_score bug fixed here)
    # ─────────────────────────────────────────────────────────────────────────

    def predict(self, input_data):
        """
        Predict adherence risk.
        input_data: dict {feature_name: value}
        Extra keys are ignored. Missing keys default to 0.

        adherence_score fix:
          Old (buggy): 1 - (label_index / 2)  → always 1.0 for 'high'
          New (fixed): low_probability + 0.5 * medium_probability
                       → proper 0.0–1.0 adherence score
        """
        if self.best_model is None:
            try:
                self.load_model()
            except FileNotFoundError:
                print("No trained models found. Training now...")
                self.train_models()

        # Build feature row
        row = {feat: input_data.get(feat, 0) for feat in self.feature_names}
        X_raw = pd.DataFrame([row])[self.feature_names].values

        # Apply scaler
        X_scaled = self.scaler.transform(X_raw) if self.scaler is not None else X_raw

        prediction       = self.best_model.predict(X_scaled)[0]
        prediction_proba = self.best_model.predict_proba(X_scaled)[0]

        risk_level = self.label_encoders['adherence_risk'].inverse_transform([prediction])[0]
        confidence = float(max(prediction_proba))

        classes    = list(self.label_encoders['adherence_risk'].classes_)
        proba_dict = {cls: float(prob) for cls, prob in zip(classes, prediction_proba)}

        # ── FIXED adherence_score ────────────────────────────────────────
        low_prob    = proba_dict.get('low', 0.0)
        medium_prob = proba_dict.get('medium', 0.0)
        adherence_score = round(low_prob + 0.5 * medium_prob, 4)

        recommendation = self._generate_recommendation(
            risk_level,
            age=input_data.get('Age', 40),
            num_medicines=input_data.get('Comorbidities_Count', 1) + 1,
            treatment_duration_days=90
        )

        return {
            'risk_level':             risk_level,
            'confidence':             confidence,
            'adherence_score':        adherence_score,
            'adherence_percentage':   round(adherence_score * 100, 1),
            'model_used':             self.best_model_name or 'Unknown',
            'recommendation':         recommendation,
            'risk_probabilities':     proba_dict,
            'selected_features_used': self.feature_names,
        }

    # ─────────────────────────────────────────────────────────────────────────
    # HELPERS
    # ─────────────────────────────────────────────────────────────────────────

    def get_selected_features(self):
        if not self.feature_names:
            try:
                self.load_model()
            except Exception:
                return []
        return self.feature_names

    def get_feature_importances(self):
        if self.feature_importances:
            return self.feature_importances
        imp_path = os.path.join(self.model_path, 'feature_importances.pkl')
        if os.path.exists(imp_path):
            with open(imp_path, 'rb') as f:
                self.feature_importances = pickle.load(f)
            return self.feature_importances
        return {}

    def _generate_recommendation(self, risk_level, age,
                                  num_medicines, treatment_duration_days):
        recommendations = {
            'low': [
                "✅ Patient shows excellent adherence potential!",
                "• Continue regular follow-ups",
                "• Provide medication schedule",
                "• Encourage maintaining current habits",
                "• Monthly check-ins sufficient"
            ],
            'medium': [
                "⚠️ Patient needs additional support for optimal adherence.",
                "• Set up daily SMS reminders",
                "• Weekly check-in calls recommended",
                "• Provide pill organizer",
                "• Monitor adherence bi-weekly",
                "• Address any barriers to adherence"
            ],
            'high': [
                "🚨 HIGH RISK - Immediate intervention critical!",
                "• Daily SMS and call reminders mandatory",
                "• Family member involvement essential",
                "• Simplify medication regimen urgently",
                "• Home visits recommended",
                "• Daily adherence monitoring",
                "• Weekly doctor consultations",
                "• Consider medication synchronization"
            ]
        }

        base = list(recommendations.get(risk_level, []))

        if age > 65:
            base.append("• Caregiver assistance recommended (age >65)")
        if num_medicines > 5:
            base.append("• Complex regimen — use medication adherence aids")
        if treatment_duration_days > 90:
            base.append("• Long-term treatment — provide ongoing motivation")

        return "\n".join(base)

    def _save_dataset_info(self, df):
        info = self.dataset_loader.get_dataset_info()
        info_path = os.path.join(self.model_path, 'dataset_info.pkl')
        with open(info_path, 'wb') as f:
            pickle.dump(info, f)

    def get_dataset_statistics(self):
        df = self.load_dataset()
        return {
            'total_samples':         len(df),
            'features_count':        len(self.feature_names),
            'feature_names':         self.feature_names,
            'risk_distribution':     df['adherence_risk'].value_counts().to_dict(),
            'age_statistics': {
                'mean': float(df['Age'].mean()),
                'min':  int(df['Age'].min()),
                'max':  int(df['Age'].max()),
                'std':  float(df['Age'].std())
            },
            'gender_distribution':   df['Gender'].value_counts().to_dict(),
            'medication_types':      df['Medication_Type'].value_counts().to_dict(),
            'severity_distribution': df['Condition_Severity'].value_counts().to_dict(),
            'dataset_source':        'Kaggle: patient_adherence_dataset.csv'
        }


# Singleton instance
predictor = AdherencePredictor()