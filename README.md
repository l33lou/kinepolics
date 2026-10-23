# KinepoliCS

Web platform for the KinepoliCS student cinema association. Centralizes movie suggestions, screening reviews, and concession stand orders.

* **Live Site:** [https://kinepolics.pages.dev/](https://kinepolics.pages.dev/)
* **API Service:** [https://kinepolics.onrender.com/](https://kinepolics.onrender.com/)

---

## Architecture

Decoupled frontend-backend architecture running on cloud infrastructure:

* **Frontend:** Vanilla JavaScript (ES6+), HTML5, CSS3 served via Cloudflare Pages CDN.
* **Backend:** Python standard library (`http.server`) web service deployed on Render.
* **Database:** SQLite 3 (`cinema.db`).
* **Integrations:** TMDB (The Movie Database) API for real-time movie search.

---

## Key Features

1. **LetterboCS:**  
View past screening history, aggregate ratings, and audience feedback word clouds.
2. **Movie Suggestions:**  
Search TMDB in real time and submit film ideas for upcoming screenings.
3. **Popcorn :**  
Select popcorn sizes and flavors (Sucré / Salé), manage cart items, and place orders.

---

## Repository Structure

```text
student-cinema/
├── server.py         # HTTP server and REST API implementation
├── database.py       # SQLite database schema, initialization, and helpers
├── test_app.py       # Automated API unit tests
├── requirements.txt  # Environment config for Render deployment
├── cinema.db         # Local SQLite database
└── public/           # Static web assets
    ├── index.html    # Single-page application markup
    ├── style.css     # Theme stylesheet
    └── app.js        # Client-side state and API request handling
```
