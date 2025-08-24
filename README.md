# CargoChains Quotation Demo (Django + DRF)

Mini project untuk membuat Quotation multi-destination (3 level: Quotation → Destination → Lines). 
Termasuk DRF nested API & template AdminLTE-style (struktur class).

## Quickstart

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

python manage.py makemigrations
python manage.py migrate

python manage.py createsuperuser

# (opsional) load sample data
python manage.py loaddata fixtures/partners.json fixtures/sales.json

python manage.py runserver
```

- Admin: http://127.0.0.1:8000/admin/
- List Quotations: http://127.0.0.1:8000/sales/quotations/
- Detail Sample: http://127.0.0.1:8000/sales/quotations/1/

## DRF API

- Base URL: `/api/quotations/`
- Contoh POST payload (multi-destination) ada di deskripsi chat sebelumnya.

Autentikasi default: Django session (login di /admin). 
Anda bisa menambahkan JWT/Token sesuai kebutuhan.
