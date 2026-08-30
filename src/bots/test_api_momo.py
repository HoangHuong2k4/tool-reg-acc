import re
import json

def extract_payment_methods(stripe_info):
    methods = []
    
    # 1. Look in payment_method_specs
    specs = stripe_info.get("payment_method_specs") or []
    for spec in specs:
        if isinstance(spec, dict) and "type" in spec:
            methods.append(spec["type"])
            
    # 2. Look in payment_method_preference -> ordered_payment_method_types
    pref = stripe_info.get("payment_method_preference") or {}
    ordered = pref.get("ordered_payment_method_types") or []
    for m in ordered:
        if m not in methods:
            methods.append(m)
            
    # 3. Look in ordered_payment_method_types at root
    root_ordered = stripe_info.get("ordered_payment_method_types") or []
    for m in root_ordered:
        if m not in methods:
            methods.append(m)
            
    return methods

def extract_trial(stripe_info):
    total_summary = stripe_info.get("total_summary") or {}
    amount_due = total_summary.get("due")
    if amount_due is None:
        amount_due = stripe_info.get("amount_total")
    try:
        amount_due = float(amount_due)
        if amount_due.is_integer():
            amount_due = int(amount_due)
    except (TypeError, ValueError):
        amount_due = None
    currency = str(stripe_info.get("currency") or total_summary.get("currency") or "vnd").upper()
    return amount_due, currency, amount_due == 0 if amount_due is not None else None
