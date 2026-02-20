from fastapi import FastAPI
from fastapi_mcp import FastApiMCP
import uvicorn
from dotenv import load_dotenv
from routers import infracost, tflint

load_dotenv()

app = FastAPI(title="Infracost MCP Server")
app.include_router(infracost.router)
app.include_router(tflint.router)


@app.get("/hello")
def say_hello(name: str = "World"):
    return {"message": f"Hello {name}!"}


mcp = FastApiMCP(app)

mcp.mount_http()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
