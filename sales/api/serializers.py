# Placeholder serializers to satisfy imports without DRF dependency.
def to_dict_quotation(q):
    return {
        "id": q.id,
        "number": q.number,
        "date": getattr(q, "date", None),
        "customer": str(getattr(q, "customer", "")),
        "business_type": getattr(q, "business_type", ""),
        "currency": getattr(q, "currency", ""),
    }
