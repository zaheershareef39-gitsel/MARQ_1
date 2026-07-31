from fastapi.testclient import TestClient

import app


def test_health_check():
    response = TestClient(app.app).get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_chat_completion_shape(monkeypatch):
    async def fake_groq(_request):
        return {
            "choices": [{"message": {"content": "Hello! How are you today?"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 2, "completion_tokens": 7, "total_tokens": 9},
        }

    monkeypatch.setattr(app, "request_groq", fake_groq)
    response = TestClient(app.app).post(
        "/chat/completions",
        json={
            "model": "masquerade-groq-chatbot",
            "messages": [{"role": "user", "content": "Hello"}],
            "stream": False,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["object"] == "chat.completion"
    assert body["choices"][0]["message"] == {"role": "assistant", "content": "Hello! How are you today?"}
