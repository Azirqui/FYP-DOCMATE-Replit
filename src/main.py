import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import uvicorn
from code_doc_ai.api import app
from dotenv import load_dotenv
load_dotenv()

# print("SUPABASE_URL:", os.getenv("SUPABASE_URL"))
# print("SUPABASE_JWT_SECRET:", os.getenv("SUPABASE_JWT_SECRET"))
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5000)
