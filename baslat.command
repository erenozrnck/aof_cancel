#!/bin/bash
cd "$(dirname "$0")"
# Tarayıcıyı aç (biraz beklemesi gerekebilir ama önce açılsa da refresh edilebilir)
open http://127.0.0.1:8000
# Sunucuyu başlat
python3 -m uvicorn server:app --reload
