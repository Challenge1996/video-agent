import uvicorn
import argparse

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='视频剪辑 Agent - Web 服务')
    parser.add_argument('--host', default='0.0.0.0', help='绑定地址')
    parser.add_argument('--port', type=int, default=8000, help='端口号')
    parser.add_argument('--no-reload', action='store_true', help='禁用热重载')
    
    args = parser.parse_args()
    
    uvicorn.run(
        "src.web.app:app",
        host=args.host,
        port=args.port,
        reload=not args.no_reload
    )
