
from typing import Dict, Any, Optional, Tuple

def calculate_risk_metrics(
    entry_price: float,
    stop_loss: float,
    take_profit: float,
    quantity: int
) -> Dict[str, Any]:
    """
    Calculate risk/reward metrics for a trade setup.
    """
    if quantity <= 0 or entry_price <= 0:
        return {}

    # Calculate basic values
    position_value = entry_price * quantity
    
    # Risk Calculations
    risk_per_share = entry_price - stop_loss
    total_risk = risk_per_share * quantity
    risk_pct = (risk_per_share / entry_price) * 100

    # Reward Calculations
    reward_per_share = take_profit - entry_price
    total_reward = reward_per_share * quantity
    reward_pct = (reward_per_share / entry_price) * 100

    # R/R Ratio
    rr_ratio = 0.0
    if risk_per_share > 0:
        rr_ratio = reward_per_share / risk_per_share
    
    # Validation / Warnings
    warnings = []
    if stop_loss >= entry_price:
        warnings.append("止损价必须低于买入价")
    if take_profit <= entry_price:
        warnings.append("止盈价必须高于买入价")
    
    return {
        "position_value": position_value,
        "risk_per_share": risk_per_share,
        "total_risk": total_risk,
        "risk_pct": risk_pct,
        "reward_per_share": reward_per_share,
        "total_reward": total_reward,
        "reward_pct": reward_pct,
        "rr_ratio": rr_ratio,
        "warnings": warnings
    }

def validate_trade_setup(entry_price: float, stop_loss: float, take_profit: float) -> Tuple[bool, str]:
    """
    Validate if the trade setup logic is sound (Long position assumption).
    """
    if entry_price <= 0:
        return False, "买入价格必须大于0"
    
    if stop_loss > 0 and stop_loss >= entry_price:
        return False, "止损价格必须低于买入价格"
        
    if take_profit > 0 and take_profit <= entry_price:
        return False, "止盈价格必须高于买入价格"
        
    return True, ""
