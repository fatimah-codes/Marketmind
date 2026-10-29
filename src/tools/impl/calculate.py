"""
MarketMind AI - Tool: calculate_metric
Section 5.2 requirement. Deterministic arithmetic in Python.
Strictly disallows eval() or dynamic expression parsing.
"""

from typing import Dict, Any, List
import math
import logging

logger = logging.getLogger("marketmind.tools.calculate")


def calculate_metric_handler(
    args: Dict[str, Any],
    context: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Perform deterministic mathematical calculation in Python.
    Returns computed result, formula, and input values.
    """
    operation = args.get("operation", "").lower().strip()
    values: List[float] = [float(v) for v in args.get("values", [])]
    period = args.get("period")
    if period is not None:
        period = float(period)

    if not values:
        return {
            "status": "error",
            "error_type": "InvalidInput",
            "message": "The 'values' array must contain at least one numeric value."
        }

    try:
        if operation == "sum":
            res = sum(values)
            formula = "sum(values)"

        elif operation == "average":
            res = sum(values) / len(values)
            formula = "sum(values) / count(values)"

        elif operation == "difference":
            if len(values) < 2:
                return {
                    "status": "error",
                    "error_type": "InsufficientOperands",
                    "message": "Difference requires at least 2 numeric values (v1 - v2)."
                }
            res = values[0] - values[1]
            formula = "values[0] - values[1]"

        elif operation == "ratio":
            if len(values) < 2:
                return {
                    "status": "error",
                    "error_type": "InsufficientOperands",
                    "message": "Ratio requires at least 2 values (numerator / denominator)."
                }
            if values[1] == 0:
                return {
                    "status": "error",
                    "error_type": "DivisionByZero",
                    "message": "Cannot compute ratio with zero denominator."
                }
            res = values[0] / values[1]
            formula = "values[0] / values[1]"

        elif operation == "growth_rate":
            if len(values) < 2:
                return {
                    "status": "error",
                    "error_type": "InsufficientOperands",
                    "message": "Growth rate requires starting and ending values [start, end]."
                }
            start_val, end_val = values[0], values[1]
            if start_val == 0:
                return {
                    "status": "error",
                    "error_type": "DivisionByZero",
                    "message": "Cannot calculate growth rate from initial value of zero."
                }
            res = ((end_val - start_val) / start_val) * 100.0
            formula = "((ending_value - starting_value) / starting_value) * 100"

        elif operation == "cagr":
            if len(values) < 2:
                return {
                    "status": "error",
                    "error_type": "InsufficientOperands",
                    "message": "CAGR requires starting and ending values [initial, final]."
                }
            if not period or period <= 0:
                return {
                    "status": "error",
                    "error_type": "MissingParameter",
                    "message": "CAGR requires a positive 'period' (number of years)."
                }
            start_val, end_val = values[0], values[1]
            if start_val <= 0 or end_val <= 0:
                return {
                    "status": "error",
                    "error_type": "InvalidDomain",
                    "message": "CAGR values must be strictly positive."
                }
            res = ((end_val / start_val) ** (1.0 / period) - 1.0) * 100.0
            formula = "((ending / starting) ** (1 / period) - 1) * 100"

        elif operation == "share":
            if len(values) < 2:
                return {
                    "status": "error",
                    "error_type": "InsufficientOperands",
                    "message": "Share requires [part, total]."
                }
            part, total = values[0], values[1]
            if total == 0:
                return {
                    "status": "error",
                    "error_type": "DivisionByZero",
                    "message": "Cannot calculate share with total of zero."
                }
            res = (part / total) * 100.0
            formula = "(part / total) * 100"

        else:
            return {
                "status": "error",
                "error_type": "UnsupportedOperation",
                "message": f"Operation '{operation}' not in supported operations enum: [growth_rate, cagr, share, ratio, average, sum, difference]"
            }

        return {
            "status": "success",
            "operation": operation,
            "inputs": values,
            "period": period,
            "formula": formula,
            "result": round(res, 4)
        }

    except Exception as e:
        logger.error(f"Error computing metric: {str(e)}")
        return {
            "status": "error",
            "error_type": "ComputationException",
            "message": f"Calculation error: {str(e)}"
        }
