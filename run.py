"""Start the service with a single Uvicorn worker."""
import uvicorn

from app.config import load_settings

if __name__ == "__main__":
    s = load_settings()
    uvicorn.run("app.main:get_app", factory=True, host=s.host, port=s.port, workers=1)
