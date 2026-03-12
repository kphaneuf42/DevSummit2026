# Smart Spatial Query (Local Version)
This FastAPI app and widget allows you to enter natural language and request spatial analyses like clustering, hotspots, or proximity to schools. Current setup uses City of Sacramento 311 Calls and Sacramento schools.

## Setup Instructions
1. Obtain OpenAI API key
3. `conda create -n spatialapi python=3.11`
4. `conda activate spatialapi`
5. `pip install -r requirements.txt`
6. Rename `env.env.template` to `.env` and paste your OpenAI key.
7. Add smart-spatial-query folder to Experience Builder Developer Edition > client > your-extensions > widgets
8. [Start Experience Builder Developer Edition](https://developers.arcgis.com/experience-builder/guide/install-guide/)
9. Start FastAPI: `uvicorn main:app --host 127.0.0.1 --port 8000 --reload`
10. Visit: [http://localhost:8000/docs](http://localhost:8000/docs)
11. Create new Experience Builder and add Smart Spatial Query widget.

