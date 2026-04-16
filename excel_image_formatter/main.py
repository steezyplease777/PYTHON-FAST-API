from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def root():
    return {"ok": True}

@app.get("/health")
def health():
    return {"status": "healthy"}

@app.post("/export")
def export():
    return {"message": "API is live"}