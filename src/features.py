GROUPS = ("room_type", "city", "day_type")


# One raw listing -> the model's columns, in the model's order
def encode(records: list[dict], columns: list[str]) -> list[list[float]]:
    rows = []
    for record in records:
        row = []
        for column in columns:
            group = next((g for g in GROUPS if column.startswith(g + "_")), None)
            if group:
                row.append(1.0 if str(record[group]) == column[len(group) + 1:] else 0.0)
            else:
                row.append(float(record[column]))
        rows.append(row)
    return rows
