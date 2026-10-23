# KinepoliCS website
This website has been created to centralise movie suggestions, movie reviews, and popcorn orders.

---

## Quick Start

1. Open your terminal in this directory:
   ```bash
   cd /home/leelou/.gemini/antigravity/scratch/student-cinema
   ```

2. Start the server:
   ```bash
   python3 server.py
   ```

3. Open your browser at:
   ```
   http://localhost:8000
   ```
---

## File Structure

```text
student-cinema/
├── server.py             # HTTP server & REST API (Python standard library)
├── database.py           # SQLite database schema, seeding, and helpers
├── test_app.py           # Automated test suite (10 test scenarios)
├── cinema.db             # Local SQLite database
├── README.md             # Project documentation
└── public/               # Frontend assets
    ├── index.html        # Single-page application markup
    ├── style.css         # Cinema dark theme stylesheet
    └── app.js            # Frontend interactivity, cart, live word cloud & admin polling
```
