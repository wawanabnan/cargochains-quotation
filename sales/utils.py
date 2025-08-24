from django.utils import timezone

def next_quotation_number(model):
    y = timezone.now().year
    prefix = f"Q-{y}-"
    last = (model.objects.filter(number__startswith=prefix)
            .order_by("-number").first())
    if not last:
        seq = 1
    else:
        try:
            seq = int(str(last.number).split("-")[-1]) + 1
        except Exception:
            seq = 1
    while True:
        cand = f"{prefix}{seq:04d}"
        if not model.objects.filter(number=cand).exists():
            return cand
        seq += 1
