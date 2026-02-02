# /// script
# dependencies = [
#   "fastapi>=0.104",
#   "uvicorn>=0.24",
# ]
# ///

from fastapi import FastAPI
import uvicorn

app = FastAPI()

@app.post("/predict")
async def predict(payload: dict):
    # Stub implementation - in a real app this would run ML inference
    return {"label": "positive", "score": 0.95}

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, log_level="info")