"""Application-time feature construction."""

from __future__ import annotations

import pandas as pd


NON_FEATURE_COLUMNS = {
    "loanId", "anon_ssn", "applicationDate", "originated", "originatedDate",
    "approved", "isFunded", "loanStatus", "fpStatus", "clarityFraudId",
    "underwritingid", "hasCF", "__index_level_0__", "_clarity_join",
    "installmentIndex", "isCollection", "paymentDate", "principal", "fees",
    "paymentAmount", "paymentStatus", "paymentReturnCode",
}


def transform_features(
    frame: pd.DataFrame,
    feature_contract: dict | None = None,
    feature_schema: dict | None = None,
) -> pd.DataFrame:
    """Apply the shared, target-independent training/inference transformation."""
    # Step 1: copy the input and parse the application timestamp safely.
    data = frame.copy()
    dates = pd.to_datetime(
        data["applicationDate"], format="mixed", errors="coerce", utc=True
    )
    if dates.isna().any():
        raise ValueError(f"Invalid applicationDate values: {int(dates.isna().sum())}")

    # Step 2: derive only application-time calendar features.
    data["application_month"] = dates.dt.month.astype("int8")
    data["application_dayofweek"] = dates.dt.dayofweek.astype("int8")
    data["application_hour"] = dates.dt.hour.astype("int8")

    # Step 3: resolve the feature contract and reject explicitly forbidden inputs.
    contract = feature_contract or {}
    contract_excluded = set(contract.get("exclude", []))
    requested = contract.get("include")
    if requested is not None:
        requested = list(requested)
        forbidden = sorted(set(requested) & NON_FEATURE_COLUMNS)
        if forbidden:
            raise ValueError(f"Feature contract requests forbidden columns: {forbidden}")

    # Step 4: remove leakage columns and apply an optional ordered allow-list.
    excluded = NON_FEATURE_COLUMNS | contract_excluded
    X = data.drop(columns=[c for c in excluded if c in data.columns])
    if requested is not None:
        missing = sorted(set(requested) - set(X.columns))
        if missing:
            raise ValueError(f"Feature contract columns are unavailable: {missing}")
        X = X[requested]

    # Step 5: require usable model inputs with supported logical data types.
    if X.empty:
        raise ValueError("Feature contract produced no model inputs")
    unsupported = X.select_dtypes(exclude=["number", "bool", "category", "string", "object"]).columns
    if len(unsupported):
        raise ValueError(f"Unsupported feature dtypes: {list(unsupported)}")

    # Step 6: convert text inputs to native categorical columns for LightGBM.
    for column in X.select_dtypes(include=["object", "string"]).columns:
        X[column] = X[column].astype("category")

    # Step 7: at inference, recreate nullable fields and enforce the saved schema.
    if feature_schema is not None:
        expected = feature_schema["features"]
        for item in expected:
            if item["name"] not in X and item.get("nullable", False):
                X[item["name"]] = pd.NA
        missing = [item["name"] for item in expected if item["name"] not in X]
        if missing:
            raise ValueError(f"Missing required model features: {missing}")
        X = X[[item["name"] for item in expected]]
        for item in expected:
            name = item["name"]
            if item["kind"] == "category":
                X[name] = pd.Categorical(X[name], categories=item.get("categories", []))
            elif item["kind"] == "bool":
                X[name] = X[name].astype("bool")
            else:
                X[name] = pd.to_numeric(X[name], errors="coerce")

    # Step 8: return the ordered matrix shared by training and serving.
    return X


def feature_schema(X: pd.DataFrame) -> dict:
    """Describe ordered model inputs and training-time category vocabularies."""
    # Step 1: inspect every feature in its trained order.
    features = []
    for name in X.columns:
        series = X[name]
        # Step 2: persist categorical vocabularies or numeric/bool logical types.
        if isinstance(series.dtype, pd.CategoricalDtype):
            features.append({
                "name": name,
                "kind": "category",
                "nullable": bool(series.isna().any()),
                "categories": [str(value) for value in series.cat.categories],
            })
        else:
            features.append({
                "name": name,
                "kind": "bool" if pd.api.types.is_bool_dtype(series) else "number",
                "nullable": bool(series.isna().any()),
            })

    # Step 3: wrap the ordered records in the versioned schema structure.
    return {"features": features}


def build_features(
    frame: pd.DataFrame,
    target: str,
    feature_contract: dict | None = None,
) -> tuple[pd.DataFrame, pd.Series]:
    """Build a labelled training matrix using the shared transformer."""
    # Step 1: fail early when the labelled dataframe lacks its target.
    if target not in frame:
        raise ValueError(f"Target column is missing: {target}")

    # Step 2: remove the target before applying the leakage-safe transformer.
    X = transform_features(frame.drop(columns=[target]), feature_contract)

    # Step 3: return aligned model inputs and an integer binary target.
    return X, frame[target].astype(int)
