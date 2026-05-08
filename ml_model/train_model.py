"""
ml_model/train_model.py — ArogyaAI ML Model Trainer

Run after placing CSVs in datasets/:
    python ml_model/train_model.py

Outputs (saved to ml_model/):
    disease_model.pkl     — RandomForestClassifier
    symptom_list.pkl      — List of 132 symptom column names
    severity_dict.pkl     — {symptom: weight} from Symptom-severity.csv
    description_dict.pkl  — {disease: description} from symptom_Description.csv
    precaution_dict.pkl   — {disease: [p1,p2,p3,p4]} from symptom_precaution.csv
"""

import os
import sys
import pickle
import pandas as pd
import numpy as np
import random
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score

# ─── Paths ────────────────────────────────────────────────────────────────────
ROOT        = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATASET_DIR = os.path.join(ROOT, "datasets")
MODEL_DIR   = os.path.dirname(os.path.abspath(__file__))

TRAINING_CSV     = os.path.join(DATASET_DIR, "Training.csv")
TESTING_CSV      = os.path.join(DATASET_DIR, "Testing.csv")
SEVERITY_CSV     = os.path.join(DATASET_DIR, "Symptom-severity.csv")
DESCRIPTION_CSV  = os.path.join(DATASET_DIR, "symptom_Description.csv")
PRECAUTION_CSV   = os.path.join(DATASET_DIR, "symptom_precaution.csv")


def save_pkl(obj, filename):
    path = os.path.join(MODEL_DIR, filename)
    with open(path, "wb") as f:
        pickle.dump(obj, f)
    print(f"  Saved: {filename}")


def check_csv(path):
    if not os.path.exists(path):
        print(f"  MISSING: {path}")
        print("     Please place all 6 CSV files in the datasets/ folder first!")
        sys.exit(1)


# ══════════════════════════════════════════════════════════════════════════════
# STEP 1: Check CSV files
# ══════════════════════════════════════════════════════════════════════════════
print("\nChecking dataset files...")
for csv_path in [TRAINING_CSV, TESTING_CSV, SEVERITY_CSV, DESCRIPTION_CSV, PRECAUTION_CSV]:
    check_csv(csv_path)
print("  All required CSV files found")


# ══════════════════════════════════════════════════════════════════════════════
# STEP 2: Load Training Data
# ══════════════════════════════════════════════════════════════════════════════
print("\nLoading training data...")
train_df = pd.read_csv(TRAINING_CSV)
test_df  = pd.read_csv(TESTING_CSV)

# Strip whitespace from column names
train_df.columns = train_df.columns.str.strip()
test_df.columns  = test_df.columns.str.strip()

# Strip whitespace from prognosis values
train_df["prognosis"] = train_df["prognosis"].str.strip()
test_df["prognosis"]  = test_df["prognosis"].str.strip()

# ─── Feature / Target split
symptom_columns = [col for col in train_df.columns if col != "prognosis"]
# Remove 'Unnamed: 133' if it exists (common in this dataset)
if 'Unnamed: 133' in symptom_columns:
    symptom_columns.remove('Unnamed: 133')

X_train = train_df[symptom_columns].fillna(0).values
y_train = train_df["prognosis"].values
X_test  = test_df[symptom_columns].fillna(0).values
y_test  = test_df["prognosis"].values

print(f"  Training samples  : {X_train.shape[0]}")
print(f"  Testing  samples  : {X_test.shape[0]}")
print(f"  Symptom features  : {len(symptom_columns)}")
print(f"  Unique diseases   : {len(set(y_train))}")
X_train_orig = X_train
y_train_orig = y_train

# ══════════════════════════════════════════════════════════════════════════════
# STEP 2.5: Data Augmentation (Symptom Dropout)
# ══════════════════════════════════════════════════════════════════════════════
print("\nAugmenting data (generating 2-3 symptom cases)...")
X_augmented = []
y_augmented = []

# For each original sample, generate subsets of symptoms
for i in range(len(X_train_orig)):
    active_indices = np.where(X_train_orig[i] == 1)[0]
    num_active = len(active_indices)
    disease = y_train_orig[i]
    
    # Add the original
    X_augmented.append(X_train_orig[i])
    y_augmented.append(disease)
    
    # AGGRESSIVE AUGMENTATION (Hackathon Winner Logic)
    # Generate 5 samples with 2 symptoms
    if num_active >= 2:
        for _ in range(5):
            sub = np.zeros(len(symptom_columns), dtype=int)
            indices = random.sample(list(active_indices), 2)
            sub[indices] = 1
            X_augmented.append(sub)
            y_augmented.append(disease)
            
    # Generate 5 samples with 3 symptoms
    if num_active >= 3:
        for _ in range(5):
            sub = np.zeros(len(symptom_columns), dtype=int)
            indices = random.sample(list(active_indices), 3)
            sub[indices] = 1
            X_augmented.append(sub)
            y_augmented.append(disease)

    # Generate 3 samples with 4 symptoms
    if num_active >= 4:
        for _ in range(3):
            sub = np.zeros(len(symptom_columns), dtype=int)
            indices = random.sample(list(active_indices), 4)
            sub[indices] = 1
            X_augmented.append(sub)
            y_augmented.append(disease)

X_train = np.array(X_augmented)
y_train = np.array(y_augmented)

print(f"  Augmented Training samples: {X_train.shape[0]}")


# ══════════════════════════════════════════════════════════════════════════════
# STEP 3: Train Random Forest
# ══════════════════════════════════════════════════════════════════════════════
print("\nTraining RandomForestClassifier (50 trees, max_depth=25 for size optimization)...")
model = RandomForestClassifier(
    n_estimators=50,
    max_depth=25,
    random_state=42,
    n_jobs=-1
)
model.fit(X_train, y_train)

# ─── Evaluate
y_pred   = model.predict(X_test)
accuracy = accuracy_score(y_test, y_pred)
print(f"  Model Accuracy on Testing.csv: {accuracy * 100:.2f}%")


# ══════════════════════════════════════════════════════════════════════════════
# STEP 4: Save model + symptom list
# ══════════════════════════════════════════════════════════════════════════════
print("\nSaving model artifacts...")
save_pkl(model,           "disease_model.pkl")
save_pkl(symptom_columns, "symptom_list.pkl")


# ══════════════════════════════════════════════════════════════════════════════
# STEP 5: Build severity dictionary from Symptom-severity.csv
# ══════════════════════════════════════════════════════════════════════════════
print("\nBuilding severity dictionary...")
sev_df  = pd.read_csv(SEVERITY_CSV)
sev_df.columns = sev_df.columns.str.strip()

# Normalize symptom names: lowercase, replace spaces with underscores
severity_dict = {}
for _, row in sev_df.iterrows():
    symptom = str(row.iloc[0]).strip().lower().replace(" ", "_")
    weight  = int(row.iloc[1])
    severity_dict[symptom] = weight

print(f"  Loaded {len(severity_dict)} symptom weights.")
save_pkl(severity_dict, "severity_dict.pkl")


# ══════════════════════════════════════════════════════════════════════════════
# STEP 6: Build disease description dictionary
# ══════════════════════════════════════════════════════════════════════════════
print("\nBuilding disease description dictionary...")
desc_df = pd.read_csv(DESCRIPTION_CSV)
desc_df.columns = desc_df.columns.str.strip()

description_dict = {}
for _, row in desc_df.iterrows():
    disease = str(row.iloc[0]).strip()
    desc    = str(row.iloc[1]).strip() if len(row) > 1 else ""
    description_dict[disease] = desc

print(f"  Loaded {len(description_dict)} disease descriptions.")
save_pkl(description_dict, "description_dict.pkl")


# ══════════════════════════════════════════════════════════════════════════════
# STEP 7: Build precaution dictionary from symptom_precaution.csv
# ══════════════════════════════════════════════════════════════════════════════
print("\nBuilding precaution dictionary...")
prec_df = pd.read_csv(PRECAUTION_CSV)
prec_df.columns = prec_df.columns.str.strip()

precaution_dict = {}
for _, row in prec_df.iterrows():
    disease = str(row.iloc[0]).strip()
    precs   = [str(row.iloc[i]).strip() for i in range(1, 5) if i < len(row) and str(row.iloc[i]).strip() not in ["", "nan"]]
    precaution_dict[disease] = precs

print(f"  Loaded precautions for {len(precaution_dict)} diseases.")
save_pkl(precaution_dict, "precaution_dict.pkl")


# ══════════════════════════════════════════════════════════════════════════════
# DONE
# ══════════════════════════════════════════════════════════════════════════════
print(f"""
--------------------------------------------------------
   ArogyaAI ML Training Complete!                    
                                                      
   Model Accuracy : {accuracy * 100:.2f}%                      
   Disease Model  : disease_model.pkl                 
   Symptom List   : symptom_list.pkl ({len(symptom_columns)} symptoms)   
   Severity Dict  : severity_dict.pkl                 
   Desc Dict      : description_dict.pkl              
   Precaution Dict: precaution_dict.pkl               
--------------------------------------------------------
""")
