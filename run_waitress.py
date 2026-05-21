from waitress import serve
from app import app

serve(
    app,
    host="0.0.0.0",
    port=5000,
    threads=12,
    connection_limit=200,
    _quiet=False
)