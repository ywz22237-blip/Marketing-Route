"""
Marketing Route 실행 스크립트
사용법: python run.py
접속:  http://localhost:8000/ui
"""
import uvicorn

if __name__ == "__main__":
    print("\n🚀 Marketing Route | AI 마케팅 네비게이터 시작")
    print("─" * 40)
    print("📊 대시보드 UI : http://localhost:8000/ui")
    print("📖 API 문서    : http://localhost:8000/docs")
    print("─" * 40)
    print("종료: Ctrl+C\n")
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=["backend"],
    )
