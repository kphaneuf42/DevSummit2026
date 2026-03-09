# Smart Spatial Query (Local Version)
This FastAPI app allows you to upload a CSV of points and request spatial analyses like clustering, hotspots, or proximity to schools.

## Setup Instructions
1. `conda create -n spatialapi python=3.11`
2. `conda activate spatialapi`
3. `pip install -r requirements.txt`
4. Rename `env.env.template` to `.env` and paste your OpenAI key.
5. Run it: `uvicorn main:app --host 127.0.0.1 --port 8000 --reload`
6. Visit: [http://localhost:8000/docs](http://localhost:8000/docs)
