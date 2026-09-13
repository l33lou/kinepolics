# update_posters.py

#temporary file to update the properties of the registered movie suggestions

import sqlite3
import json
import urllib.request
import urllib.parse

TMDB_API_KEY = "36714c952f9cd9e486626a91fd3d16fe"

conn = sqlite3.connect("cinema.db")
cursor = conn.cursor()

cursor.execute("SELECT id, title FROM movies")
movies = cursor.fetchall()

for movie_id, title in movies:
    query = urllib.parse.quote(title)
    url = f"https://api.themoviedb.org/3/search/movie?api_key={TMDB_API_KEY}&query={query}&language=fr-FR"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("results"):
                m = data["results"][0]
                poster = f"https://image.tmdb.org/t/p/w500{m['poster_path']}" if m.get("poster_path") else None
                synopsis = m.get("overview")
                if poster:
                    cursor.execute("UPDATE movies SET poster_url = ?, synopsis = COALESCE(NULLIF(synopsis, ''), ?) WHERE id = ?", (poster, synopsis, movie_id))
                    print(f"✅ Mis à jour : {title}")
    except Exception as e:
        print(f"❌ Erreur {title}: {e}")

conn.commit()
conn.close()
print("Terminé !")