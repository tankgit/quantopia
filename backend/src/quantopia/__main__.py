"""
主入口文件
"""
import uvicorn

if __name__ == "__main__":
    uvicorn.run("src.quantopia.api:app", host="0.0.0.0", port=15000, reload=True)

