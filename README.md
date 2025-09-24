curl.exe -X POST "http://127.0.0.1:8000/search" -H "Content-Type: application/json" -d "{\"query\": \"医療DX\", \"top_k\": 5}"

curl.exe -X POST "https://gov-meeting-rag.vercel.app/api/search" -H "Content-Type: application/json" -d "{\"query\": \"医療DX\", \"top_k\": 5}"

