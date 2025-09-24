from fastapi import FastAPI
from mangum import Mangum  # AWS Lambda互換のASGIアダプタ

from main import app  # ← いまのFastAPIアプリをそのまま使う

# Vercel/Lambda 用のハンドラ
handler = Mangum(app)
