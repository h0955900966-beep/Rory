"""Calculate group costs using explicit FX inputs and room occupancy."""
from __future__ import annotations

import argparse
import json
from decimal import Decimal, InvalidOperation, ROUND_CEILING, ROUND_HALF_UP
from pathlib import Path
from typing import Any


def decimal_value(value: Any, label: str, *, positive: bool = False) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise ValueError(f"{label}: provide a number")
    try:
        number = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError(f"{label}: invalid number") from exc
    if not number.is_finite() or number < 0 or (positive and number == 0):
        raise ValueError(f"{label}: provide a finite {'positive' if positive else 'nonnegative'} number")
    return number


def integer_value(value: Any, label: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise ValueError(f"{label}: provide an integer >= {minimum}")
    return value


def money(value: Decimal) -> str:
    return format(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), "f")


def calculate(data: dict) -> dict:
    if not isinstance(data, dict):
        raise ValueError("input must be a JSON object")
    travelers = integer_value(data["travelers"], "travelers", 1)
    singles = integer_value(data.get("single_travelers", 0), "single_travelers")
    nights = integer_value(data["nights"], "nights")
    if singles > travelers or (travelers - singles) % 2:
        raise ValueError("single_travelers must leave an even number of twin-sharing travelers")
    vnd_rate = decimal_value(data["vnd_per_1000_twd"], "vnd_per_1000_twd", positive=True)
    usd_rate = decimal_value(data["twd_per_usd"], "twd_per_usd", positive=True)
    margin = decimal_value(data.get("margin_percent", 0), "margin_percent") / 100
    if margin >= 1:
        raise ValueError("margin_percent must be less than 100")
    rounding = decimal_value(data.get("quote_round_to_twd", 1), "quote_round_to_twd", positive=True)

    def convert(value: Decimal, currency: str) -> Decimal:
        if currency == "TWD":
            return value
        if currency == "VND":
            return value * 1000 / vnd_rate
        if currency == "USD":
            return value * usd_rate
        raise ValueError(f"unsupported currency: {currency!r}; use TWD, VND, USD")

    costs = data.get("cost_lines", [])
    if not isinstance(costs, list):
        raise ValueError("cost_lines must be a list")
    lines = []
    other_cost = Decimal(0)
    for index, item in enumerate(costs):
        if not isinstance(item, dict):
            raise ValueError(f"cost_lines[{index}] must be an object")
        label = str(item["label"])
        amount = decimal_value(item["amount"], f"{label}.amount")
        quantity = decimal_value(item["quantity"], f"{label}.quantity", positive=True)
        line_cost = convert(amount * quantity, item["currency"])
        other_cost += line_cost
        lines.append({"label": label, "currency": item["currency"],
                      "amount": str(amount), "quantity": str(quantity),
                      "total_twd": money(line_cost)})

    hotel = data["hotel"]
    twin_rate = convert(decimal_value(hotel["twin_room_per_night"], "twin_room_per_night"), hotel["currency"])
    single_rate = convert(decimal_value(hotel["single_room_per_night"], "single_room_per_night"), hotel["currency"])
    twin_rooms = (travelers - singles) // 2
    hotel_cost = nights * (twin_rooms * twin_rate + singles * single_rate)
    total_cost = other_cost + hotel_cost
    twin_person_cost = other_cost / travelers + nights * twin_rate / 2
    single_person_cost = other_cost / travelers + nights * single_rate

    def selling_price(cost: Decimal) -> Decimal:
        return (cost / (1 - margin) / rounding).to_integral_value(rounding=ROUND_CEILING) * rounding

    twin_quote = selling_price(twin_person_cost)
    single_quote = selling_price(single_person_cost)
    revenue = twin_quote * (travelers - singles) + single_quote * singles
    profit = revenue - total_cost
    achieved_margin = profit / revenue * 100 if revenue else Decimal(0)
    return {
        "currency": "TWD", "travelers": travelers, "single_travelers": singles,
        "nights": nights, "rooms": {"twin": twin_rooms, "single": singles},
        "fx_inputs": {"vnd_per_1000_twd": str(vnd_rate), "twd_per_usd": str(usd_rate)},
        "conversion": "VND to TWD = VND * 1000 / vnd_per_1000_twd; USD to TWD = USD * twd_per_usd",
        "cost_lines": lines, "nonhotel_cost_twd": money(other_cost),
        "hotel_cost_twd": money(hotel_cost), "total_cost_twd": money(total_cost),
        "twin_cost_per_person_twd": money(twin_person_cost),
        "single_cost_per_person_twd": money(single_person_cost),
        "twin_quote_per_person_twd": money(twin_quote),
        "single_quote_per_person_twd": money(single_quote),
        "single_room_supplement_twd": money(single_quote - twin_quote),
        "total_revenue_twd": money(revenue), "gross_profit_twd": money(profit),
        "target_margin_percent": money(margin * 100),
        "achieved_margin_percent": money(achieved_margin),
        "note": "User-supplied FX and costs. Quantities cover the entire group. Tax and tips are included only when entered as cost lines."
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        data = json.loads(args.input.read_text(encoding="utf-8-sig"), parse_float=Decimal)
        result = calculate(data)
    except (ValueError, KeyError, TypeError, OSError, InvalidOperation) as exc:
        parser.exit(2, f"Quote input error: {exc}\n")
    output = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(output, encoding="utf-8")
    else:
        print(output, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
