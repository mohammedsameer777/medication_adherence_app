"""
ML Service — AdherencePredictor
================================
XGBoost FORCED as primary model. 89-92% accuracy target.
Dataset: 5k real + 10k augmented (3% Gaussian noise) = 15k total.
Features: 13 original → 34 engineered → top 20 via RFE.

FIXES IN THIS VERSION (inference path only — training logic unchanged):
1. engineer_features() division-by-zero on single-row DataFrames when
   Comorbidities_Count / education_encoded / mental_health_encoded = 0.
2. predict() KeyError when all_engineered_cols pkl is empty or mismatched.
3. predict() ValueError when rfe_selector gets wrong feature count.
4. load_model() gives actionable error on XGBoost version mismatch.
5. predictor singleton wrapped in lazy-init to avoid startup crash.
"""

import os
import pickle

import numpy as np
import pandas as pd
from django.conf import settings
from sklearn.ensemble import (
    GradientBoostingClassifier,
    RandomForestClassifier,
)
from sklearn.feature_selection import RFE
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.model_selection import (
    StratifiedKFold,
    cross_val_score,
    train_test_split,
)
from sklearn.neighbors import KNeighborsClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import LabelEncoder, StandardScaler
import xgboost as xgb

from .data_loader import DatasetLoader

try:
    from imblearn.over_sampling import SMOTE
    SMOTE_AVAILABLE = True
except ImportError:
    SMOTE_AVAILABLE = False
    print("⚠️  Run: pip install imbalanced-learn")

try:
    import lightgbm as lgb
    LGBM_AVAILABLE = True
except ImportError:
    LGBM_AVAILABLE = False


class AdherencePredictor:
    """
    ML service — XGBoost FORCED as primary model.
    Dataset: 5k real + 10k augmented (3% noise) = 15k total.
    Target: 89-92% accuracy with XGBoost.
    """

    def __init__(self):
        self.models              = {}
        self.label_encoders      = {}
        self.scaler              = None
        self.best_model          = None
        self.best_model_name     = None
        self.feature_names       = []
        self.all_engineered_cols = []
        self.feature_importances = {}
        self.rfe_selector        = None
        self.dataset_loader      = DatasetLoader()

        # FIX: guard makedirs — settings.BASE_DIR must be resolved first
        try:
            self.model_path = os.path.join(settings.BASE_DIR, 'ml_models')
            if not os.path.exists(self.model_path):
                os.makedirs(self.model_path)
        except Exception as e:
            print(f"⚠️  ml_models directory init failed: {e}")
            self.model_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)), '..', 'ml_models')

    # ─────────────────────────────────────────────────────────────────────────
    # DATASET  (unchanged)
    # ─────────────────────────────────────────────────────────────────────────

    def load_dataset(self):
        df = self.dataset_loader.load_dataset()
        if df is None:
            raise Exception("Failed to load Kaggle dataset")
        if not self.dataset_loader.validate_dataset(df):
            raise Exception("Dataset validation failed")
        df = self.dataset_loader.preprocess_dataset(df)
        print(f"✅ Real Kaggle dataset loaded: {len(df)} records")

        print("⚙️  Augmenting dataset (3x with 3% noise → 15k records)...")
        np.random.seed(42)
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        noise_cols   = [c for c in numeric_cols
                        if c not in ['adherence_risk', 'Adherence']]

        augmented_parts = [df]
        for _ in range(2):
            df_aug = df.copy()
            for col in noise_cols:
                std = df[col].std()
                if std > 0:
                    df_aug[col] = (df_aug[col]
                                   + np.random.normal(0, std * 0.03, len(df_aug)))
            augmented_parts.append(df_aug)

        df_final = pd.concat(augmented_parts, ignore_index=True)
        print(f"✅ Final dataset: {len(df_final)} records")
        for risk, count in df_final['adherence_risk'].value_counts().items():
            print(f"      {risk}: {count} ({count/len(df_final)*100:.1f}%)")
        return df_final

    # ─────────────────────────────────────────────────────────────────────────
    # FEATURE ENGINEERING — 34 features  (unchanged except division-by-zero fix)
    # ─────────────────────────────────────────────────────────────────────────

    def engineer_features(self, df):
        df = df.copy()

        # FIX: use max(…, 1) so single-row inference with 0-valued columns
        # never produces division-by-zero in the engineered features.
        # Training behaviour is identical because the training dataset always
        # has at least one non-zero value in these columns.
        comorbidity_max = float(max(df['Comorbidities_Count'].max(), 1))
        education_max   = float(max(df['education_encoded'].max(),   1))
        mental_max      = float(max(df['mental_health_encoded'].max(), 1))

        df['vulnerability_score'] = (
            (df['Age'] / 100) * 0.4
            + (df['severity_encoded'] / 2) * 0.6
        )
        df['support_gap'] = (
            (1 - df['social_support_encoded'] / 2)
            * (df['Comorbidities_Count'] / comorbidity_max)
        )
        df['adherence_capacity'] = (
            df['income_normalized'] * 0.35
            + (df['education_encoded'] / education_max) * 0.35
            + (df['healthcare_access_encoded'] / 2) * 0.30
        )
        df['stress_index'] = (
            (1 - df['mental_health_encoded'] / mental_max)
            * (1 - df['income_normalized'])
        )
        df['dosage_burden']        = df['dosage_normalized'] * (df['Age'] / 100)
        df['history_support']      = (df['Previous_Adherence']
                                      * (df['social_support_encoded'] / 2))
        df['comorbidity_severity'] = (df['Comorbidities_Count']
                                      * (df['severity_encoded'] + 1))
        df['risk_composite'] = (
            (1 - df['Previous_Adherence']) * 0.30
            + (df['severity_encoded'] / 2) * 0.20
            + (df['Comorbidities_Count'] / comorbidity_max) * 0.15
            + (1 - df['income_normalized']) * 0.15
            + (1 - df['healthcare_access_encoded'] / 2) * 0.10
            + (1 - df['mental_health_encoded'] / mental_max) * 0.10
        )
        df['adherence_risk_score'] = (
            df['Previous_Adherence'] * 0.40
            + df['income_normalized'] * 0.20
            + (df['healthcare_access_encoded'] / 2) * 0.20
            + (1 - df['severity_encoded'] / 2) * 0.20
        )
        df['barrier_index'] = (
            (1 - df['income_normalized']) * 0.30
            + df['support_gap'] * 0.30
            + df['stress_index'] * 0.20
            + (df['Comorbidities_Count'] / comorbidity_max) * 0.20
        )
        df['protective_score'] = (
            df['Previous_Adherence'] * 0.35
            + df['history_support'] * 0.25
            + df['adherence_capacity'] * 0.25
            + df['Insurance_Coverage'] * 0.15
        )
        df['combined_risk']  = df['risk_composite'] * (1 - df['protective_score'])
        df['net_risk_score'] = df['barrier_index'] - df['protective_score']

        df['income_x_adherence']  = (df['income_normalized']
                                     * df['Previous_Adherence'])
        df['severity_x_comorbid'] = (
            (df['severity_encoded'] / 2)
            * (df['Comorbidities_Count'] / comorbidity_max)
        )
        df['access_x_support']    = (
            (df['healthcare_access_encoded'] / 2)
            * (df['social_support_encoded'] / 2)
        )
        df['dosage_x_severity']   = (
            df['dosage_normalized']
            * (df['severity_encoded'] / 2 + 0.001)
        )
        df['age_x_comorbid']      = (
            (df['Age'] / 100)
            * (df['Comorbidities_Count'] / comorbidity_max)
        )
        df['mental_x_income']     = (
            (df['mental_health_encoded'] / mental_max)
            * df['income_normalized']
        )
        df['prev_adh_x_severity'] = (
            df['Previous_Adherence']
            * (1 - df['severity_encoded'] / 2)
        )
        df['insurance_x_income']  = (
            df['Insurance_Coverage'] * df['income_normalized']
        )

        return df

    # ─────────────────────────────────────────────────────────────────────────
    # FEATURE PREP  (unchanged)
    # ─────────────────────────────────────────────────────────────────────────

    def prepare_features(self, df):
        original_features = [
            'Age', 'gender_encoded', 'medication_type_encoded',
            'dosage_normalized', 'Previous_Adherence', 'education_encoded',
            'income_normalized', 'social_support_encoded', 'severity_encoded',
            'Comorbidities_Count', 'healthcare_access_encoded',
            'mental_health_encoded', 'Insurance_Coverage',
        ]
        engineered_features = [
            'vulnerability_score', 'support_gap', 'adherence_capacity',
            'stress_index', 'dosage_burden', 'history_support',
            'comorbidity_severity', 'risk_composite',
            'adherence_risk_score', 'barrier_index', 'protective_score',
            'combined_risk', 'net_risk_score',
            'income_x_adherence', 'severity_x_comorbid', 'access_x_support',
            'dosage_x_severity', 'age_x_comorbid', 'mental_x_income',
            'prev_adh_x_severity', 'insurance_x_income',
        ]
        all_features             = original_features + engineered_features
        self.all_engineered_cols = all_features

        if 'adherence_risk' not in self.label_encoders:
            self.label_encoders['adherence_risk'] = LabelEncoder()
            y = self.label_encoders['adherence_risk'].fit_transform(
                df['adherence_risk'])
        else:
            y = self.label_encoders['adherence_risk'].transform(
                df['adherence_risk'])

        X_all = df[all_features].fillna(0)

        print(f"\n📊 Computing importances on all {len(all_features)} features...")
        imp_rf = RandomForestClassifier(
            n_estimators=300, max_depth=None,
            random_state=42, n_jobs=-1, class_weight='balanced',
        )
        imp_rf.fit(X_all, y)
        self.feature_importances = {
            feat: float(imp_rf.feature_importances_[i])
            for i, feat in enumerate(all_features)
        }

        print(f"\n🔍 RFE → top 20 of {len(all_features)}...")
        self.rfe_selector = RFE(
            estimator=RandomForestClassifier(
                n_estimators=300, max_depth=None,
                random_state=42, n_jobs=-1, class_weight='balanced',
            ),
            n_features_to_select=20,
            step=1,
        )
        self.rfe_selector.fit(X_all, y)

        selected_mask      = self.rfe_selector.support_
        self.feature_names = [f for f, s in zip(all_features, selected_mask) if s]
        rejected           = [f for f, s in zip(all_features, selected_mask) if not s]

        print(f"\n✅ Selected ({len(self.feature_names)}): {self.feature_names}")
        print(f"   Removed  ({len(rejected)}): {rejected}")

        X_selected = self.rfe_selector.transform(X_all)

        if SMOTE_AVAILABLE:
            print("\n⚖️  Applying SMOTE...")
            print(f"   Before: {dict(pd.Series(y).value_counts())}")
            try:
                X_selected, y = SMOTE(
                    random_state=42, k_neighbors=5).fit_resample(X_selected, y)
                print(f"   After:  {dict(pd.Series(y).value_counts())}")
            except Exception as e:
                print(f"   ⚠️  SMOTE failed: {e}")

        self.scaler = StandardScaler()
        X_scaled    = self.scaler.fit_transform(X_selected)

        return X_scaled, y

    # ─────────────────────────────────────────────────────────────────────────
    # TRAINING — XGBoost FORCED as primary  (unchanged)
    # ─────────────────────────────────────────────────────────────────────────

    def train_models(self):
        print("\n" + "=" * 70)
        print("TRAINING MEDICATION ADHERENCE PREDICTION MODELS")
        print("Version 9.1 — XGBoost FORCED as Primary Model")
        print("=" * 70)

        print("\n📂 Loading dataset...")
        df = self.load_dataset()

        print("\n⚙️  Engineering features...")
        df = self.engineer_features(df)

        print("\n🔧 Running RFE + SMOTE + scaling...")
        X, y = self.prepare_features(df)

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y)
        print(f"\n   Training: {len(X_train)} | Testing: {len(X_test)}")

        cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

        models_to_train = {
            'XGBoost': xgb.XGBClassifier(
                n_estimators=500, learning_rate=0.05, max_depth=6,
                subsample=0.8, colsample_bytree=0.8,
                reg_alpha=0.1, reg_lambda=1.0, min_child_weight=5,
                random_state=42, eval_metric='mlogloss', n_jobs=-1,
            ),
            'Random Forest': RandomForestClassifier(
                n_estimators=500, max_depth=12, min_samples_split=5,
                min_samples_leaf=2, max_features='sqrt',
                random_state=42, class_weight='balanced',
                n_jobs=-1, oob_score=True,
            ),
            'Gradient Boosting': GradientBoostingClassifier(
                n_estimators=500, learning_rate=0.05, max_depth=5,
                subsample=0.8, min_samples_split=5, random_state=42,
            ),
            'MLP Neural Net': MLPClassifier(
                hidden_layer_sizes=(128, 64), activation='relu',
                solver='adam', alpha=0.01, batch_size=64,
                learning_rate='adaptive', learning_rate_init=0.001,
                max_iter=300, random_state=42,
                early_stopping=True, validation_fraction=0.1,
                n_iter_no_change=20,
            ),
            'KNN': KNeighborsClassifier(
                n_neighbors=15, weights='uniform',
                metric='manhattan', n_jobs=-1,
            ),
            'Logistic Regression': LogisticRegression(
                max_iter=3000, C=1.0, solver='lbfgs',
                class_weight='balanced', random_state=42,
            ),
        }

        if LGBM_AVAILABLE:
            models_to_train['LightGBM'] = lgb.LGBMClassifier(
                n_estimators=500, learning_rate=0.05, max_depth=6,
                num_leaves=31, subsample=0.8, colsample_bytree=0.8,
                min_child_samples=30, class_weight='balanced',
                random_state=42, n_jobs=-1, verbose=-1,
            )

        results = []
        print("\n" + "=" * 70)
        print("MODEL TRAINING RESULTS")
        print("=" * 70)

        for name, model in models_to_train.items():
            print(f"\n🤖 Training {name}...")
            try:
                model.fit(X_train, y_train)
                y_pred    = model.predict(X_test)
                accuracy  = accuracy_score(y_test, y_pred)
                precision = precision_score(
                    y_test, y_pred, average='weighted', zero_division=0)
                recall    = recall_score(
                    y_test, y_pred, average='weighted', zero_division=0)
                f1        = f1_score(
                    y_test, y_pred, average='weighted', zero_division=0)
                cv_scores = cross_val_score(
                    model, X, y, cv=cv, scoring='f1_weighted', n_jobs=-1)

                print(f"   ✅ Accuracy:       {accuracy  * 100:.2f}%")
                print(f"   ✅ Precision:      {precision * 100:.2f}%")
                print(f"   ✅ Recall:         {recall    * 100:.2f}%")
                print(f"   ✅ F1 Score:       {f1        * 100:.2f}%")
                print(f"   ✅ CV F1 (5-fold): "
                      f"{cv_scores.mean()*100:.2f}% ± {cv_scores.std()*100:.2f}%")

                if hasattr(model, 'oob_score_'):
                    print(f"   ✅ OOB Score:      {model.oob_score_*100:.2f}%")

                labels = self.label_encoders['adherence_risk'].classes_
                print(f"\n   Classification Report:\n   "
                      + classification_report(
                          y_test, y_pred,
                          target_names=labels, zero_division=0,
                      ).replace('\n', '\n   '))

                results.append({
                    'model_name':       name,
                    'model':            model,
                    'accuracy':         accuracy,
                    'precision':        precision,
                    'recall':           recall,
                    'f1_score':         f1,
                    'cv_f1_mean':       cv_scores.mean(),
                    'confusion_matrix': confusion_matrix(y_test, y_pred),
                })
                self.models[name] = model

            except Exception as e:
                print(f"   ❌ {name} failed: {e}")

        # ── Leaderboard ───────────────────────────────────────────────────────
        results.sort(key=lambda x: x['f1_score'], reverse=True)
        print("\n" + "=" * 70)
        print("📊 LEADERBOARD")
        print("=" * 70)
        print(f"{'Rank':<5} {'Model':<25} {'Accuracy':>10} "
              f"{'F1':>10} {'CV F1':>10}")
        print("-" * 65)
        for i, r in enumerate(results, 1):
            flag = (" 🏆" if r['model_name'] == 'XGBoost'
                    else (" ⭐" if r['f1_score'] >= 0.90 else ""))
            print(f"{i:<5} {r['model_name']:<25} "
                  f"{r['accuracy']*100:>9.2f}% "
                  f"{r['f1_score']*100:>9.2f}% "
                  f"{r['cv_f1_mean']*100:>9.2f}%{flag}")

        # ── FORCE XGBoost as best model ───────────────────────────────────────
        xgb_result = next(
            (r for r in results if r['model_name'] == 'XGBoost'), None)
        if xgb_result is None:
            print("⚠️  XGBoost training failed — falling back to top model")
            xgb_result = results[0]
            self.best_model_name = xgb_result['model_name']
        else:
            self.best_model_name = 'XGBoost'

        self.best_model = xgb_result['model']
        best_result     = xgb_result

        print("\n" + "=" * 70)
        print("🏆 BEST MODEL SELECTED (FORCED)")
        print("=" * 70)
        print(f"   Model:     {self.best_model_name}")
        print(f"   Accuracy:  {best_result['accuracy']  * 100:.2f}%")
        print(f"   Precision: {best_result['precision'] * 100:.2f}%")
        print(f"   Recall:    {best_result['recall']    * 100:.2f}%")
        print(f"   F1 Score:  {best_result['f1_score']  * 100:.2f}%")
        print(f"\n   Dataset:   15k records (5k real + 10k augmented at 3% noise)")
        print(f"   Features:  20 selected from 34 engineered via RFE")
        print("=" * 70 + "\n")

        self.save_model(self.best_model, self.best_model_name)
        self._save_dataset_info(df)
        return results

    # ─────────────────────────────────────────────────────────────────────────
    # SAVE / LOAD
    # ─────────────────────────────────────────────────────────────────────────

    def save_model(self, model, model_name):
        filename      = f"{model_name.replace(' ', '_').lower()}_model.pkl"
        files_to_save = {
            filename:                  model,
            'label_encoders.pkl':      self.label_encoders,
            'feature_names.pkl':       self.feature_names,
            'feature_importances.pkl': self.feature_importances,
            'scaler.pkl':              self.scaler,
            'rfe_selector.pkl':        self.rfe_selector,
            'all_engineered_cols.pkl': self.all_engineered_cols,
        }
        for fname, obj in files_to_save.items():
            with open(os.path.join(self.model_path, fname), 'wb') as f:
                pickle.dump(obj, f)
        print(f"✅ Model saved: {os.path.join(self.model_path, filename)}")

    def load_model(self, model_name=None):
        if model_name is None:
            model_files = [f for f in os.listdir(self.model_path)
                           if f.endswith('_model.pkl')]
            if not model_files:
                raise FileNotFoundError("No trained models found.")
            xgb_file = 'xgboost_model.pkl'
            if xgb_file in model_files:
                filename   = xgb_file
                model_name = 'XGBoost'
            else:
                filename   = model_files[0]
                model_name = (filename.replace('_model.pkl', '')
                              .replace('_', ' ').title())
        else:
            filename = f"{model_name.replace(' ', '_').lower()}_model.pkl"

        def _load(fname):
            path = os.path.join(self.model_path, fname)
            if os.path.exists(path):
                with open(path, 'rb') as f:
                    return pickle.load(f)
            return None

        # FIX: catch XGBoost version mismatch with an actionable message
        try:
            model = _load(filename)
        except Exception as e:
            raise RuntimeError(
                f"Failed to load model '{filename}': {e}\n"
                f"This usually means the .pkl was saved with a different "
                f"XGBoost version. Re-train via POST /api/predictions/models/train/"
            ) from e

        if model is None:
            raise FileNotFoundError(f"Model file not found: {filename}")

        self.label_encoders      = _load('label_encoders.pkl')      or {}
        self.feature_names       = _load('feature_names.pkl')       or []
        self.feature_importances = _load('feature_importances.pkl') or {}
        self.scaler              = _load('scaler.pkl')
        self.rfe_selector        = _load('rfe_selector.pkl')
        self.all_engineered_cols = _load('all_engineered_cols.pkl') or []
        self.best_model          = model
        self.best_model_name     = model_name

        print(f"✅ Model loaded: {filename}")
        return model

    # ─────────────────────────────────────────────────────────────────────────
    # PREDICTION  (inference bugs fixed — output identical to before)
    # ─────────────────────────────────────────────────────────────────────────

    def predict(self, input_data):
        if self.best_model is None:
            try:
                self.load_model()
            except (FileNotFoundError, RuntimeError):
                self.train_models()

        original_features = [
            'Age', 'gender_encoded', 'medication_type_encoded',
            'dosage_normalized', 'Previous_Adherence', 'education_encoded',
            'income_normalized', 'social_support_encoded', 'severity_encoded',
            'Comorbidities_Count', 'healthcare_access_encoded',
            'mental_health_encoded', 'Insurance_Coverage',
        ]

        # Build single-row DataFrame from input
        row    = {feat: input_data.get(feat, 0) for feat in original_features}
        df_row = pd.DataFrame([row])

        # Engineer all 34 features
        df_row = self.engineer_features(df_row)

        # FIX: validate all_engineered_cols before indexing
        if not self.all_engineered_cols:
            raise RuntimeError(
                "all_engineered_cols is empty — model may not be loaded. "
                "Re-train via POST /api/predictions/models/train/"
            )

        # FIX: ensure every expected column is present; fill missing with 0
        for col in self.all_engineered_cols:
            if col not in df_row.columns:
                df_row[col] = 0.0

        X_raw = df_row[self.all_engineered_cols].fillna(0).values

        # FIX: validate RFE selector input shape before transform
        if self.rfe_selector is not None:
            expected_cols = len(self.all_engineered_cols)
            actual_cols   = X_raw.shape[1]
            if actual_cols != expected_cols:
                raise RuntimeError(
                    f"Feature shape mismatch: rfe_selector expects "
                    f"{expected_cols} features but got {actual_cols}. "
                    f"Re-train via POST /api/predictions/models/train/"
                )
            X_rfe = self.rfe_selector.transform(X_raw)
        else:
            X_rfe = X_raw

        # Scale
        X_scaled = self.scaler.transform(X_rfe) if self.scaler else X_rfe

        # Predict
        prediction       = self.best_model.predict(X_scaled)[0]
        prediction_proba = self.best_model.predict_proba(X_scaled)[0]

        risk_level = self.label_encoders['adherence_risk'].inverse_transform(
            [prediction])[0]
        confidence = float(max(prediction_proba))
        classes    = list(self.label_encoders['adherence_risk'].classes_)
        proba_dict = {cls: float(prob)
                      for cls, prob in zip(classes, prediction_proba)}

        low_prob        = proba_dict.get('low',    0.0)
        medium_prob     = proba_dict.get('medium', 0.0)
        adherence_score = round(low_prob + 0.5 * medium_prob, 4)

        recommendation = self._generate_recommendation(
            risk_level,
            age=input_data.get('Age', 40),
            num_medicines=input_data.get('Comorbidities_Count', 1) + 1,
            treatment_duration_days=90,
        )

        return {
            'risk_level':             risk_level,
            'confidence':             confidence,
            'adherence_score':        adherence_score,
            'adherence_percentage':   round(adherence_score * 100, 1),
            'model_used':             self.best_model_name or 'XGBoost',
            'recommendation':         recommendation,
            'risk_probabilities':     proba_dict,
            'selected_features_used': self.feature_names,
        }

    # ─────────────────────────────────────────────────────────────────────────
    # HELPERS  (unchanged)
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

    def _generate_recommendation(self, risk_level, age,
                                  num_medicines, treatment_duration_days):
        recommendations = {
            'low': [
                "✅ Patient shows excellent adherence potential!",
                "• Continue regular follow-ups",
                "• Provide medication schedule",
                "• Encourage maintaining current habits",
                "• Monthly check-ins sufficient",
            ],
            'medium': [
                "⚠️ Patient needs additional support for optimal adherence.",
                "• Set up daily SMS reminders",
                "• Weekly check-in calls recommended",
                "• Provide pill organizer",
                "• Monitor adherence bi-weekly",
                "• Address any barriers to adherence",
            ],
            'high': [
                "🚨 HIGH RISK — Immediate intervention critical!",
                "• Daily SMS and call reminders mandatory",
                "• Family member involvement essential",
                "• Simplify medication regimen urgently",
                "• Home visits recommended",
                "• Daily adherence monitoring",
                "• Weekly doctor consultations",
                "• Consider medication synchronization",
            ],
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
        info_path = os.path.join(self.model_path, 'dataset_info.pkl')
        with open(info_path, 'wb') as f:
            pickle.dump(self.dataset_loader.get_dataset_info(), f)

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
                'std':  float(df['Age'].std()),
            },
            'gender_distribution':   df['Gender'].value_counts().to_dict(),
            'medication_types':      df['Medication_Type'].value_counts().to_dict(),
            'severity_distribution': df['Condition_Severity'].value_counts().to_dict(),
            'dataset_source': (
                'Kaggle: patient_adherence_dataset.csv '
                '(5k real + augmented)'
            ),
        }


# ── Singleton instance ────────────────────────────────────────────────────────
# FIX: wrapped in try/except — makedirs or settings resolution failure during
# Django startup should not prevent the app from starting.
try:
    predictor = AdherencePredictor()
except Exception as _e:
    print(f"⚠️  AdherencePredictor init failed at startup: {_e}")
    predictor = AdherencePredictor.__new__(AdherencePredictor)
    predictor.models              = {}
    predictor.label_encoders      = {}
    predictor.scaler              = None
    predictor.best_model          = None
    predictor.best_model_name     = None
    predictor.feature_names       = []
    predictor.all_engineered_cols = []
    predictor.feature_importances = {}
    predictor.rfe_selector        = None
    predictor.dataset_loader      = DatasetLoader()
    predictor.model_path          = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), '..', 'ml_models')