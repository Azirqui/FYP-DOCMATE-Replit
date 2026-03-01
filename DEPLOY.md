# Deploy to Vercel

## Quick Deploy

1. Push this repo to GitHub
2. Go to [vercel.com](https://vercel.com) and create a new project
3. Import your GitHub repository
4. Vercel auto-detects `vercel.json` configuration
5. Add environment variables in Settings → Environment Variables

## Environment Variables

Set these in the Vercel dashboard:

| Variable | Required | Description |
|----------|----------|-------------|
| `GROQ_API_KEY` | Optional | For Groq/Llama AI documentation |
| `GOOGLE_API_KEY` | Optional | For Google Gemini AI documentation |

At least one API key is needed for AI-powered documentation features. Without API keys, code analysis and UML generation still work.

## Verify Deployment

After deployment, test the API:

```bash
curl https://your-project.vercel.app/api/v1/health
```

Access Swagger docs at: `https://your-project.vercel.app/docs`

## How It Works

- `vercel.json` - Configures Python runtime and routes all requests to the API
- `api/index.py` - Entry point that imports the FastAPI app
- `requirements.txt` - Python dependencies installed automatically

## Serverless Notes

- Vercel runs Python as serverless functions
- Each request spins up a fresh instance (no persistent state)
- Cold starts may add ~1-2 seconds on first request
- Use databases (not in-memory storage) for any state
- Free tier has 100GB bandwidth/month

## Local Testing

```bash
cd src && python main.py
```

Then visit http://localhost:5000/docs
