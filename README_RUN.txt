运行方式（Windows / macOS / Linux）

1) 进入项目目录
   cd guestbook

2) 创建虚拟环境并安装依赖
   python -m venv .venv

   Windows PowerShell:
     .\.venv\Scripts\Activate.ps1
   macOS/Linux:
     source .venv/bin/activate

   pip install -r requirements.txt

3) 运行
   python app.py

4) 访问
   用户端：  http://127.0.0.1:5000/
   管理端：  http://127.0.0.1:5000/admin226

部署建议
- 线上部署请把 app.py 里的 debug=True 改为 False。
- 管理端目前只有“隐藏路径”，建议加密码（我可以下一步帮你加）。
- 图片目录：guestbook/static/uploads
- 数据库：guestbook/database.db
