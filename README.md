# Smart Spatial Query (Local Version)
This FastAPI app and widget allows you to enter natural language and request spatial analyses like clustering, hotspots, or proximity to schools. Current setup uses City of Sacramento 311 Calls and Sacramento schools.

## Setup Instructions
1. `conda create -n spatialapi python=3.11`
2. `conda activate spatialapi`
3. `pip install -r requirements.txt`
4. Rename `env.env.template` to `.env` and paste your OpenAI key.
5. Add smart-spatial-query folder to Experience Builder Developer Edition > client > your-extensions > widgets
6. [Start Experience Builder Developer Edition](https://developers.arcgis.com/experience-builder/guide/install-guide/)
7. Start FastAPI: `uvicorn main:app --host 127.0.0.1 --port 8000 --reload`
8. Visit: [http://localhost:8000/docs](http://localhost:8000/docs)
9. Create new Experience Builder and add Smart Spatial Query widget.

