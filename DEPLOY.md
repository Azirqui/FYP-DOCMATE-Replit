# Deploy to Vercel

## Quick Deploy

1. Push this repo to GitHub
2. Go to [vercel.com](https://vercel.com) and create a new project
3. Import your GitHub repository
4. Vercel auto-detects `vercel.json` configuration
5. Add environment variables in Settings → Environment Variables

## Environment Variables

Set these in the Vercel dashboard (Settings → Environment Variables):

| Variable | Required | Description |
|----------|----------|-------------|
| `GROQ_API_KEY` | Yes* | For Groq/Llama AI documentation generation |
| `GOOGLE_API_KEY` | Yes* | For Google Gemini AI documentation editing |
| `SUPABASE_URL` | Yes | Your Supabase project URL (e.g., https://xxxxx.supabase.co) |
| `SUPABASE_JWT_SECRET` | Yes | Supabase Dashboard → Settings → API → JWT Secret |
| `SUPABASE_SERVICE_KEY` | Yes | Supabase Dashboard → Settings → API → service_role key |
| `DAILY_GENERATION_LIMIT` | No | Daily rate limit per user (default: 50) |

*At least one LLM API key is needed for AI documentation features. Without API keys, code analysis and UML generation still work.

## Database Setup

Before deploying, run the SQL migration in your Supabase project:

1. Go to Supabase Dashboard → SQL Editor
2. Copy and paste the contents of `migrations/001_create_tables.sql`
3. Run the query

This creates the `projects`, `project_files`, `generated_docs`, and `generated_uml` tables with Row Level Security.

## Verify Deployment

After deployment, test the API:

```bash
curl https://your-project.vercel.app/api/v1/health
```

Access Swagger docs at: `https://your-project.vercel.app/docs`

## How It Works

- `vercel.json` - Configures Python runtime and routes all requests to the API
- `api/index.py` - Entry point that imports the FastAPI app
- `api/requirements.txt` - Python dependencies installed automatically
- All code lives in `code_doc_ai/` package — shared between local dev and Vercel

## Serverless Notes

- Vercel runs Python as serverless functions
- Each request spins up a fresh instance (no persistent state)
- Cold starts may add ~1-2 seconds on first request
- All state is stored in Supabase (projects, docs, usage logs)
- Free tier has 100GB bandwidth/month

## Local Development

```bash
cd src && python main.py
```

Then visit http://localhost:5000/docs

## Authentication

All endpoints (except `/api/v1/health`) require a Supabase JWT token:
1. Sign up/in via Supabase Auth (frontend handles this)
2. Get the JWT access token
3. Send it as `Authorization: Bearer <token>` header
