# 🚀 UFC Elo Rating System - 24/7 Cloud Deployment Guide

This project is completely packaged and ready for free 24/7 deployment to **Render.com**, **Railway**, or **PythonAnywhere**.

---

## 🌟 Method 1: Deploy to Render.com (Recommended - 100% Free & Automatic)

Render provides a free Web Service tier that will keep your UFC Elo dashboard online 24/7 with a public HTTPS URL (e.g. `https://ufc-elo.onrender.com`).

### Steps:
1. **Push your code to GitHub**:
   - Go to [github.com/new](https://github.com/new) and create a repository named `ufc-elo-system`.
   - Upload the project files (`app.py`, `Procfile`, `requirements.txt`, `render.yaml`, `fighter_rankings.json`, `matches.json`, `elo_history.json`, and the `templates/` folder).

2. **Deploy on Render**:
   - Go to [dashboard.render.com](https://dashboard.render.com/) (Sign in with GitHub).
   - Click **"New +"** $\rightarrow$ **"Web Service"**.
   - Select your `ufc-elo-system` repository.
   - Render will automatically detect the settings from `render.yaml` and `Procfile`:
     - **Environment**: `Python 3`
     - **Build Command**: `pip install -r requirements.txt`
     - **Start Command**: `gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --threads 4 --timeout 120`
     - **Instance Type**: `Free`
   - Click **"Create Web Service"**.

3. **Done!** In ~1-2 minutes, your live dashboard will be available at your custom Render URL!

---

## 🐍 Method 2: Deploy to PythonAnywhere (No Git Required)

If you prefer uploading the folder directly without using GitHub:

1. Create a free account at [pythonanywhere.com](https://www.pythonanywhere.com).
2. Go to the **"Web"** tab $\rightarrow$ Click **"Add a new web app"**.
3. Choose **Flask** and **Python 3.10+**.
4. In the **"Files"** tab, upload:
   - `app.py`
   - `fighter_rankings.json`
   - `matches.json`
   - `elo_history.json`
   - `templates/index.html` (inside a `templates` folder)
5. In the **"Bash Console"**, install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
6. Click **"Reload"** on your Web tab. Your app is live at `https://yourusername.pythonanywhere.com`!

---

## 🚂 Method 3: Deploy to Railway.app

1. Go to [railway.app](https://railway.app/) $\rightarrow$ Click **"New Project"**.
2. Select **"Deploy from GitHub repo"** and choose `ufc-elo-system`.
3. Railway will automatically detect the `Procfile` and deploy your app.
4. In **Settings** $\rightarrow$ **Networking**, click **"Generate Domain"** to get your public live URL.

---

## 📦 Packaged Configuration Files Summary

| File | Description |
| :--- | :--- |
| [`Procfile`](file:///C:/Users/sinan/.gemini/antigravity-ide/scratch/ufc-elo-system/Procfile) | Production WSGI command with Gunicorn worker/thread pooling |
| [`render.yaml`](file:///C:/Users/sinan/.gemini/antigravity-ide/scratch/ufc-elo-system/render.yaml) | Render Infrastructure-as-Code Blueprint |
| [`requirements.txt`](file:///C:/Users/sinan/.gemini/antigravity-ide/scratch/ufc-elo-system/requirements.txt) | Python dependencies (`flask`, `gunicorn`, `requests`, `beautifulsoup4`, `pandas`) |
| [`.gitignore`](file:///C:/Users/sinan/.gemini/antigravity-ide/scratch/ufc-elo-system/.gitignore) | Excludes local virtual environment and temporary cache files |
