# MASQUERADE '26 - Groq Backend

This is a backend-only chatbot for MASQUERADE '26. It uses **Groq**, not the OpenAI API, to generate replies. Its public route uses the OpenAI Chat Completions shape solely because that is the judging platform's required contract.

## Required route

`POST /chat/completions`

The endpoint accepts the full `messages` history and returns the required `choices[0].message.content` reply. Streaming is disabled because the submission guide specifies non-streaming requests.

## Run locally

1. Create a Groq API key in the Groq Console.
2. Copy `.env.example` to `.env` and fill in `GROQ_API_KEY`.
3. Install dependencies:

   ```powershell
   python -m pip install -r requirements.txt
   ```

4. Start the service:

   ```powershell
   $env:GROQ_API_KEY = "gsk_your_real_key"
   $env:JUDGE_API_KEY = "a-long-random-secret" # optional
   uvicorn app:app --host 0.0.0.0 --port 8000
   ```

5. Test it:

   ```powershell
   curl.exe http://127.0.0.1:8000/chat/completions `
     -H "Content-Type: application/json" `
     -H "Authorization: Bearer a-long-random-secret" `
     -d '{"model":"masquerade-groq-chatbot","messages":[{"role":"user","content":"Hello"}],"stream":false}'
   ```

If `JUDGE_API_KEY` is not set, omit the `Authorization` header.

## Deploy to Render

1. Create a Render **Web Service** from this repository. Render will use `render.yaml`; alternatively set build command to `pip install -r requirements.txt` and start command to `uvicorn app:app --host 0.0.0.0 --port $PORT`.
2. In Render's Environment settings, add `GROQ_API_KEY` with your real Groq key. Never put this key in code or Git.
3. Keep the generated `JUDGE_API_KEY` to protect the endpoint, then copy it to the submission form. Or remove it and submit `none` as API Key.
4. Verify `https://YOUR-SERVICE.onrender.com/` returns a success response.
5. Test `https://YOUR-SERVICE.onrender.com/chat/completions` with the command above.

## MASQUERADE submission values

| Form field | Value |
| --- | --- |
| Team / Participant Name | Your team name |
| Endpoint Base URL | `https://YOUR-SERVICE.onrender.com` |
| API Key | `JUDGE_API_KEY`, or `none` if not configured |
| Model Name | `masquerade-groq-chatbot` (or your `PUBLIC_MODEL_NAME`) |

Do **not** add `/chat/completions` to the submitted base URL; the judges append it.
