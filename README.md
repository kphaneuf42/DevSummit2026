# Smart Spatial Query (Local Version)
This FastAPI app and widget allows you to enter natural language and request spatial analyses like clustering, hotspots, or proximity to schools. Current setup uses City of Sacramento 311 Calls and Sacramento schools.

## Setup Instructions
1. Obtain OpenAI API key
2. Create a web map with the following layers:
    [Sacramento 311 Calls](https://services5.arcgis.com/54falWtcpty3V47Z/arcgis/rest/services/SalesForce311_View/FeatureServer/0)
    [Sacramento Schools](https://services5.arcgis.com/54falWtcpty3V47Z/arcgis/rest/services/Schools/FeatureServer/0)
4. `conda create -n spatialapi python=3.11`
5. `conda activate spatialapi`
6. `pip install -r requirements.txt`
7. Rename `env.env.template` to `.env` and paste your OpenAI key.
8. Add smart-spatial-query folder to Experience Builder Developer Edition > client > your-extensions > widgets
9. [Start Experience Builder Developer Edition](https://developers.arcgis.com/experience-builder/guide/install-guide/)
10. Start FastAPI: `uvicorn main:app --host 127.0.0.1 --port 8000 --reload`
11. Visit: [http://localhost:8000/docs](http://localhost:8000/docs)
12. Create new Experience Builder, add your web map, and add Smart Spatial Query widget.

