import http.server
import socketserver
import json
import os
import mimetypes
import urllib.parse
import random
import string
from database import get_db, init_db
import urllib.request
import urllib.parse

PORT = 8000
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PUBLIC_DIR = os.path.join(BASE_DIR, "public")
VISUALS_DIR = os.path.join(BASE_DIR, "visuals")
ADMIN_PIN = "1234"  # Default association admin PIN

class CinemaRequestHandler(http.server.BaseHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PATCH, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Admin-Pin")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def send_json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def parse_json_body(self):
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length == 0:
            return {}
        body = self.rfile.read(content_length).decode("utf-8")
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            return None

    def check_admin_auth(self):
        # Checks X-Admin-Pin header
        pin = self.headers.get("X-Admin-Pin", "")
        return pin == ADMIN_PIN

    def do_GET(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        query = urllib.parse.parse_qs(parsed_url.query)

        # API Routes
        if path == "/api/movies":
            self.handle_get_movies()
        elif path == "/api/tmdb/search":  # <-- AJOUTER CETTE ROUTE
            query_str = query.get("query", [""])[0]
            self.handle_get_tmdb_search(query_str)
        elif path == "/api/products":
            self.handle_get_products()
        elif path == "/api/orders":
            customer = query.get("customer", [None])[0]
            self.handle_get_orders(customer_name=customer)
        elif path.startswith("/api/orders/"):
            code_or_id = path[len("/api/orders/"):]
            self.handle_get_single_order(code_or_id)
        elif path == "/api/admin/stats":
            self.handle_get_admin_stats()
        elif path == "/api/admin/verify":
            # Quick PIN check
            pin = query.get("pin", [""])[0]
            self.send_json({"valid": pin == ADMIN_PIN})
        elif path == "/api/reviews":
            movie_id = query.get("movie_id", [None])[0]
            self.handle_get_reviews(movie_id)
        elif path == "/api/wordcloud":
            movie_id = query.get("movie_id", [None])[0]
            self.handle_get_wordcloud(movie_id)
        else:
            # Serve static files
            self.serve_static(path)

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path

        if path == "/api/vote":
            self.handle_post_vote()
        elif path in ("/api/movies/suggest", "/api/movies"):
            self.handle_post_suggest_movie()
        elif path.startswith("/api/movies/") and path.endswith("/screened"):
            parts = path.strip("/").split("/")
            if len(parts) >= 3:
                self.handle_post_increment_screened(parts[2])
            else:
                self.send_json({"error": "Invalid URL"}, 400)
        elif path == "/api/orders":
            self.handle_post_order()
        elif path == "/api/reviews":
            self.handle_post_review()
        elif path == "/api/wordcloud":
            self.handle_post_wordcloud()
        elif path == "/api/admin/movies":
            if not self.check_admin_auth():
                return self.send_json({"error": "Unauthorized. Invalid Admin PIN."}, 401)
            self.handle_admin_add_movie()
        elif path == "/api/admin/reset":
            if not self.check_admin_auth():
                return self.send_json({"error": "Unauthorized. Invalid Admin PIN."}, 401)
            self.handle_admin_reset()
        else:
            self.send_json({"error": "Endpoint not found"}, 404)

    def do_PATCH(self):
        path = urllib.parse.urlparse(self.path).path
        if path.startswith("/api/orders/"):
            order_id = path[len("/api/orders/"):]
            self.handle_patch_order(order_id)
        else:
            self.send_json({"error": "Endpoint not found"}, 404)

    def do_DELETE(self):
        path = urllib.parse.urlparse(self.path).path
        if path.startswith("/api/orders/"):
            order_id = path[len("/api/orders/"):]
            self.handle_delete_order(order_id)
        elif path.startswith("/api/reviews/"):
            review_id = path[len("/api/reviews/"):]
            self.handle_delete_review(review_id)
        elif path.startswith("/api/wordcloud/"):
            word_id = path[len("/api/wordcloud/"):]
            self.handle_delete_wordcloud(word_id)
        elif path.startswith("/api/admin/movies/"):
            if not self.check_admin_auth():
                return self.send_json({"error": "Unauthorized. Invalid Admin PIN."}, 401)
            movie_id = path[len("/api/admin/movies/"):]
            self.handle_admin_delete_movie(movie_id)
        else:
            self.send_json({"error": "Endpoint not found"}, 404)

    # ----------------- Movie & Voting Handlers -----------------

    def handle_get_movies(self):
        parsed = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(parsed.query)
        genre = qs.get("genre", [None])[0]
        screened = qs.get("screened", [None])[0]
        search = qs.get("search", [None])[0]

        conn = get_db()
        cursor = conn.cursor()

        where_clauses = ["m.is_active = 1"]
        params = []

        if genre and genre.lower() not in ("all", "tous"):
            where_clauses.append("LOWER(m.genre) LIKE ?")
            params.append(f"%{genre.lower()}%")

        if screened in ("true", "yes", "1"):
            where_clauses.append("m.screened_count > 0")
        elif screened in ("false", "no", "0"):
            where_clauses.append("(m.screened_count = 0 OR m.screened_count IS NULL)")

        if search:
            where_clauses.append("(LOWER(m.title) LIKE ? OR LOWER(m.synopsis) LIKE ?)")
            params.extend([f"%{search.lower()}%", f"%{search.lower()}%"])

        sql = f"""
            SELECT m.*, 
                   COUNT(v.id) AS vote_count
            FROM movies m
            LEFT JOIN votes v ON m.id = v.movie_id
            WHERE {" AND ".join(where_clauses)}
            GROUP BY m.id
            ORDER BY vote_count DESC, m.screened_count DESC, m.title ASC
        """
        cursor.execute(sql, params)
        movies = [dict(row) for row in cursor.fetchall()]
        
        # Calculate total votes
        total_votes = sum(m["vote_count"] for m in movies)
        for m in movies:
            m["percentage"] = round((m["vote_count"] / total_votes * 100), 1) if total_votes > 0 else 0

        # Unique genre list
        cursor.execute("SELECT DISTINCT genre FROM movies WHERE is_active = 1 AND genre IS NOT NULL")
        genres = [r["genre"] for r in cursor.fetchall() if r["genre"]]

        conn.close()
        self.send_json({
            "movies": movies,
            "total_votes": total_votes,
            "genres": genres
        })

    def handle_get_tmdb_search(self, query):
            """Recherche en direct sur TMDB pour l'autocomplétion de la modale."""
            if not query or len(query.strip()) < 2:
                return self.send_json({"results": []})

            if not TMDB_API_KEY or TMDB_API_KEY == "TA_CLE_API_TMDB_ICI":
                return self.send_json({"results": []})

            try:
                encoded_query = urllib.parse.quote(query.strip())
                url = f"https://api.themoviedb.org/3/search/movie?api_key={TMDB_API_KEY}&query={encoded_query}&language=fr-FR"
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})

                with urllib.request.urlopen(req, timeout=5) as response:
                    data = json.loads(response.read().decode("utf-8"))
                    raw_results = data.get("results", [])[:5]  # Limiter aux 5 premiers candidats

                    candidates = []
                    for m in raw_results:
                        poster_path = m.get("poster_path")
                        release_date = m.get("release_date", "")
                        year = int(release_date.split("-")[0]) if release_date and len(release_date) >= 4 else None

                        candidates.append({
                            "id": m.get("id"),
                            "title": m.get("title") or m.get("original_title"),
                            "year": year,
                            "synopsis": m.get("overview") or "Aucun synopsis disponible.",
                            "poster_url": f"https://image.tmdb.org/t/p/w500{poster_path}" if poster_path else "https://images.unsplash.com/photo-1489599849927-2ee91cede3ba?w=600"
                        })

                    return self.send_json({"results": candidates})
            except Exception as e:
                print(f"Erreur recherche TMDB : {e}")
                return self.send_json({"results": []})

    def handle_post_suggest_movie(self):
        data = self.parse_json_body()
        if not data:
            return self.send_json({"error": "Corps JSON invalide"}, 400)

        title = str(data.get("title", "")).strip()
        if not title:
            return self.send_json({"error": "Le titre du film est obligatoire."}, 400)

        suggested_by = str(data.get("suggested_by", "")).strip() or None
        year = data.get("year")
        synopsis = str(data.get("synopsis", "Aucun synopsis disponible.")).strip()
        poster_url = str(data.get("poster_url", "")).strip() or "https://images.unsplash.com/photo-1489599849927-2ee91cede3ba?w=600"

        conn = get_db()
        cursor = conn.cursor()

        # Vérifier si le film existe déjà en BDD
        cursor.execute("SELECT id, title FROM movies WHERE LOWER(title) = LOWER(?)", (title,))
        existing = cursor.fetchone()
        if existing:
            conn.close()
            return self.send_json({
                "success": False,
                "already_exists": True,
                "message": f"« {existing['title']} » est déjà dans la liste des suggestions !"
            }, 200)

        cursor.execute("""
            INSERT INTO movies (title, year, genre, runtime, synopsis, poster_url, screened_count, suggested_by, is_active)
            VALUES (?, ?, 'Films cultes', '2h 00m', ?, ?, 0, ?, 1)
        """, (title, year, synopsis, poster_url, suggested_by))

        conn.commit()
        movie_id = cursor.lastrowid
        conn.close()

        self.send_json({
            "success": True,
            "movie_id": movie_id,
            "message": f"✨ « {title} » a été ajouté aux suggestions !"
        }, 201)

    def handle_post_vote(self):
        data = self.parse_json_body()
        if not data:
            return self.send_json({"error": "Invalid JSON body"}, 400)

        voter_name = str(data.get("voter_name", "")).strip()
        movie_id = data.get("movie_id")

        if not voter_name:
            return self.send_json({"error": "Please enter your name or username to vote."}, 400)
        if not movie_id:
            return self.send_json({"error": "Please select a movie to vote for."}, 400)

        conn = get_db()
        cursor = conn.cursor()

        # Check if user already voted
        cursor.execute("SELECT id, movie_id FROM votes WHERE LOWER(voter_name) = LOWER(?)", (voter_name,))
        existing_vote = cursor.fetchone()

        if existing_vote:
            # Change vote or prevent? Let's allow changing vote with clear message
            cursor.execute("UPDATE votes SET movie_id = ?, created_at = CURRENT_TIMESTAMP WHERE id = ?", 
                        (movie_id, existing_vote["id"]))
            conn.commit()
            conn.close()
            return self.send_json({
                "success": True,
                "message": f"Your vote has been updated for '{voter_name}'!",
                "updated": True
            })
        else:
            cursor.execute("INSERT INTO votes (voter_name, movie_id) VALUES (?, ?)", (voter_name, movie_id))
            conn.commit()
            conn.close()
            return self.send_json({
                "success": True,
                "message": f"Thank you, {voter_name}! Your vote has been recorded.",
                "updated": False
            })

    # ----------------- Snack Products & Orders Handlers -----------------

    def handle_get_products(self):
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM products WHERE is_available = 1 ORDER BY category ASC, price ASC")
        products = [dict(row) for row in cursor.fetchall()]
        conn.close()
        self.send_json({"products": products})

    def handle_post_order(self):
        data = self.parse_json_body()
        if not data:
            return self.send_json({"error": "Invalid request body"}, 400)

        customer_name = str(data.get("customer_name", "")).strip()
        items = data.get("items", [])
        notes = data.get("notes", "")

        if not customer_name:
            return self.send_json({"error": "Please provide your name for order pickup."}, 400)
        if not items or len(items) == 0:
            return self.send_json({"error": "Your cart is empty."}, 400)

        conn = get_db()
        cursor = conn.cursor()

        # Calculate exact total from database to prevent price manipulation
        total_price = 0.0
        validated_items = []
        for it in items:
            p_id = it.get("product_id")
            qty = int(it.get("quantity", 1))
            if qty <= 0:
                continue
            cursor.execute("SELECT * FROM products WHERE id = ? AND is_available = 1", (p_id,))
            prod = cursor.fetchone()
            if prod:
                item_total = prod["price"] * qty
                total_price += item_total
                validated_items.append({
                    "product_id": prod["id"],
                    "product_name": prod["name"],
                    "quantity": qty,
                    "unit_price": prod["price"]
                })

        if not validated_items:
            conn.close()
            return self.send_json({"error": "No valid products found in cart."}, 400)

        # Generate friendly order code, e.g. POP-492
        num = random.randint(100, 999)
        order_code = f"POP-{num}"

        # Insert order
        cursor.execute("""
            INSERT INTO orders (order_code, customer_name, total_price, is_paid, status, notes)
            VALUES (?, ?, ?, 0, 'pending', ?)
        """, (order_code, customer_name, round(total_price, 2), notes))
        order_id = cursor.lastrowid

        # Insert order items
        for it in validated_items:
            cursor.execute("""
                INSERT INTO order_items (order_id, product_id, product_name, quantity, unit_price)
                VALUES (?, ?, ?, ?, ?)
            """, (order_id, it["product_id"], it["product_name"], it["quantity"], it["unit_price"]))

        conn.commit()
        conn.close()

        self.send_json({
            "success": True,
            "order": {
                "id": order_id,
                "order_code": order_code,
                "customer_name": customer_name,
                "total_price": round(total_price, 2),
                "status": "pending",
                "is_paid": 0,
                "items": validated_items
            }
        }, 201)

    def handle_get_orders(self, customer_name=None):
        conn = get_db()
        cursor = conn.cursor()

        if customer_name:
            cursor.execute("""
                SELECT * FROM orders 
                WHERE LOWER(customer_name) = LOWER(?) 
                ORDER BY created_at DESC
            """, (customer_name.strip(),))
        else:
            cursor.execute("SELECT * FROM orders ORDER BY created_at DESC")

        orders = [dict(row) for row in cursor.fetchall()]

        # Fetch items for each order
        for ord_obj in orders:
            cursor.execute("SELECT * FROM order_items WHERE order_id = ?", (ord_obj["id"],))
            ord_obj["items"] = [dict(it) for it in cursor.fetchall()]

        conn.close()
        self.send_json({"orders": orders})

    def handle_get_single_order(self, code_or_id):
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM orders WHERE order_code = ? OR id = ?", (code_or_id, code_or_id))
        order = cursor.fetchone()
        if not order:
            conn.close()
            return self.send_json({"error": "Order not found"}, 404)

        order_data = dict(order)
        cursor.execute("SELECT * FROM order_items WHERE order_id = ?", (order_data["id"],))
        order_data["items"] = [dict(it) for it in cursor.fetchall()]
        conn.close()
        self.send_json({"order": order_data})

    def handle_patch_order(self, order_id):
        data = self.parse_json_body()
        if data is None:
            return self.send_json({"error": "Invalid request body"}, 400)

        conn = get_db()
        cursor = conn.cursor()

        updates = []
        params = []
        if "is_paid" in data:
            updates.append("is_paid = ?")
            params.append(1 if data["is_paid"] else 0)
        if "status" in data:
            updates.append("status = ?")
            params.append(str(data["status"]))

        if not updates:
            conn.close()
            return self.send_json({"error": "No fields to update"}, 400)

        params.append(order_id)
        query = f"UPDATE orders SET {', '.join(updates)} WHERE id = ?"
        cursor.execute(query, params)
        conn.commit()

        cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
        updated_row = cursor.fetchone()
        conn.close()

        if not updated_row:
            return self.send_json({"error": "Order not found"}, 404)

        self.send_json({"success": True, "order": dict(updated_row)})

    def handle_delete_order(self, order_id):
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM orders WHERE id = ?", (order_id,))
        conn.commit()
        conn.close()
        self.send_json({"success": True, "message": "Order deleted."})

    # ----------------- Admin Analytics & Management -----------------

    def handle_get_admin_stats(self):
        conn = get_db()
        cursor = conn.cursor()

        # Unique voters
        cursor.execute("SELECT DISTINCT LOWER(voter_name) as name FROM votes")
        voters = {row["name"] for row in cursor.fetchall()}

        # Unique snack buyers
        cursor.execute("SELECT DISTINCT LOWER(customer_name) as name FROM orders")
        buyers = {row["name"] for row in cursor.fetchall()}

        # Unique total attendees (voters union buyers)
        attendees = voters.union(buyers)

        # Revenue totals
        cursor.execute("SELECT SUM(total_price) as total_rev, COUNT(id) as total_orders FROM orders")
        rev_row = cursor.fetchone()
        total_revenue = rev_row["total_rev"] or 0.0
        total_orders = rev_row["total_orders"] or 0

        cursor.execute("SELECT SUM(total_price) as paid_rev FROM orders WHERE is_paid = 1")
        paid_row = cursor.fetchone()
        paid_revenue = paid_row["paid_rev"] or 0.0

        # Total votes
        cursor.execute("SELECT COUNT(id) as total_votes FROM votes")
        total_votes = cursor.fetchone()["total_votes"]

        # Popular snack items
        cursor.execute("""
            SELECT product_name, SUM(quantity) as total_qty, SUM(quantity * unit_price) as total_item_rev
            FROM order_items
            GROUP BY product_name
            ORDER BY total_qty DESC
            LIMIT 5
        """)
        top_snacks = [dict(row) for row in cursor.fetchall()]

        # Orders summary status
        cursor.execute("SELECT status, COUNT(id) as count FROM orders GROUP BY status")
        order_status_counts = {row["status"]: row["count"] for row in cursor.fetchall()}

        conn.close()

        self.send_json({
            "total_attendees": len(attendees),
            "unique_voters": len(voters),
            "unique_buyers": len(buyers),
            "total_votes": total_votes,
            "total_orders": total_orders,
            "total_revenue": round(total_revenue, 2),
            "paid_revenue": round(paid_revenue, 2),
            "unpaid_revenue": round(total_revenue - paid_revenue, 2),
            "top_snacks": top_snacks,
            "order_status_counts": order_status_counts
        })

    def handle_admin_add_movie(self):
        data = self.parse_json_body()
        if not data:
            return self.send_json({"error": "Invalid request body"}, 400)

        title = str(data.get("title", "")).strip()
        if not title:
            return self.send_json({"error": "Movie title is required."}, 400)

        year = int(data.get("year", 2024))
        genre = str(data.get("genre", "Cinema Selection"))
        runtime = str(data.get("runtime", "2h 00m"))
        synopsis = str(data.get("synopsis", "Candidate film for the upcoming student movie night."))
        poster_url = str(data.get("poster_url", "https://images.unsplash.com/photo-1489599849927-2ee91cede3ba?w=600&auto=format&fit=crop&q=80"))

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO movies (title, year, genre, runtime, synopsis, poster_url, is_active)
            VALUES (?, ?, ?, ?, ?, ?, 1)
        """, (title, year, genre, runtime, synopsis, poster_url))
        conn.commit()
        movie_id = cursor.lastrowid
        conn.close()

        self.send_json({"success": True, "movie_id": movie_id, "message": f"Added '{title}' to nominations!"}, 201)

    def handle_admin_delete_movie(self, movie_id):
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM movies WHERE id = ?", (movie_id,))
        conn.commit()
        conn.close()
        self.send_json({"success": True, "message": "Movie removed from nominations."})

    def handle_admin_reset(self):
        conn = get_db()
        cursor = conn.cursor()
        # Reset votes, orders, reviews and word clouds for a brand new movie night
        cursor.execute("DELETE FROM votes")
        cursor.execute("DELETE FROM order_items")
        cursor.execute("DELETE FROM orders")
        cursor.execute("DELETE FROM reviews")
        cursor.execute("DELETE FROM word_cloud")
        conn.commit()
        conn.close()
        self.send_json({"success": True, "message": "Movie night reset successfully! Votes, orders, reviews, and word cloud cleared."})

    # ----------------- Letterboxd-style Reviews Handlers -----------------

    def handle_get_reviews(self, movie_id=None):
        conn = get_db()
        cursor = conn.cursor()

        query = """
            SELECT r.*, m.title as movie_title, m.poster_url as movie_poster
            FROM reviews r
            JOIN movies m ON r.movie_id = m.id
        """
        params = []
        if movie_id:
            query += " WHERE r.movie_id = ?"
            params.append(movie_id)
        
        query += " ORDER BY r.created_at DESC"
        cursor.execute(query, params)
        reviews = [dict(row) for row in cursor.fetchall()]

        # Calculate average rating & star distribution
        avg_rating = 0.0
        total_reviews = len(reviews)
        star_counts = {5: 0, 4: 0, 3: 0, 2: 0, 1: 0}

        if total_reviews > 0:
            total_score = sum(r["rating"] for r in reviews)
            avg_rating = round(total_score / total_reviews, 1)
            for r in reviews:
                rounded_star = min(5, max(1, round(r["rating"])))
                star_counts[rounded_star] = star_counts.get(rounded_star, 0) + 1

        conn.close()
        self.send_json({
            "reviews": reviews,
            "total_reviews": total_reviews,
            "avg_rating": avg_rating,
            "star_distribution": star_counts
        })

    def handle_post_review(self):
        data = self.parse_json_body()
        if not data:
            return self.send_json({"error": "Invalid JSON body"}, 400)

        reviewer_name = str(data.get("reviewer_name", "")).strip()
        movie_id = data.get("movie_id")
        try:
            rating = float(data.get("rating", 5.0))
        except (ValueError, TypeError):
            rating = 5.0

        review_text = str(data.get("review_text", "")).strip()

        if not reviewer_name:
            return self.send_json({"error": "Please enter your name or nickname."}, 400)
        if not movie_id:
            return self.send_json({"error": "Movie ID is required."}, 400)
        if rating < 0.5 or rating > 5.0:
            return self.send_json({"error": "Rating must be between 1 and 5 stars."}, 400)

        conn = get_db()
        cursor = conn.cursor()

        # Check if user already reviewed this movie, update if so
        cursor.execute("SELECT id FROM reviews WHERE movie_id = ? AND LOWER(reviewer_name) = LOWER(?)", 
                       (movie_id, reviewer_name))
        existing = cursor.fetchone()

        if existing:
            cursor.execute("""
                UPDATE reviews 
                SET rating = ?, review_text = ?, created_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (rating, review_text, existing["id"]))
            conn.commit()
            review_id = existing["id"]
            updated = True
        else:
            cursor.execute("""
                INSERT INTO reviews (movie_id, reviewer_name, rating, review_text)
                VALUES (?, ?, ?, ?)
            """, (movie_id, reviewer_name, rating, review_text))
            conn.commit()
            review_id = cursor.lastrowid
            updated = False

        conn.close()
        self.send_json({
            "success": True,
            "review_id": review_id,
            "updated": updated,
            "message": "Review updated!" if updated else "Review posted! Thanks for your thoughts."
        }, 201)

    def handle_delete_review(self, review_id):
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM reviews WHERE id = ?", (review_id,))
        conn.commit()
        conn.close()
        self.send_json({"success": True, "message": "Review deleted."})

    # ----------------- Wooclap-style Word Cloud Handlers -----------------

    def handle_get_wordcloud(self, movie_id=None):
        conn = get_db()
        cursor = conn.cursor()

        query = """
            SELECT LOWER(TRIM(word)) as clean_word,
                   MAX(word) as display_word,
                   COUNT(id) as count
            FROM word_cloud
        """
        params = []
        if movie_id:
            query += " WHERE movie_id = ?"
            params.append(movie_id)

        query += " GROUP BY clean_word ORDER BY count DESC, clean_word ASC LIMIT 80"
        cursor.execute(query, params)
        raw_words = cursor.fetchall()

        words = []
        for row in raw_words:
            words.append({
                "word": row["display_word"],
                "count": row["count"]
            })

        total_submissions = sum(w["count"] for w in words)
        conn.close()

        self.send_json({
            "words": words,
            "total_submissions": total_submissions
        })

    def handle_post_wordcloud(self):
        data = self.parse_json_body()
        if not data:
            return self.send_json({"error": "Invalid request body"}, 400)

        word = str(data.get("word", "")).strip()
        movie_id = data.get("movie_id")
        contributor = str(data.get("contributor_name", "Anonymous")).strip()

        # Clean word (strip basic punctuation, cap at 35 chars)
        word = word.strip(" !.,?\"'#:;~*&^%$@()[]{}").strip()
        if not word:
            return self.send_json({"error": "Please enter a word or feeling."}, 400)
        if len(word) > 40:
            return self.send_json({"error": "Keep it punchy (under 40 characters)!"}, 400)

        # Title-case single words or short phrases for clean visual cloud
        if len(word.split()) <= 2:
            display_word = word.title()
        else:
            display_word = word

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO word_cloud (movie_id, contributor_name, word)
            VALUES (?, ?, ?)
        """, (movie_id, contributor, display_word))
        conn.commit()
        word_id = cursor.lastrowid
        conn.close()

        self.send_json({
            "success": True,
            "word_id": word_id,
            "word": display_word,
            "message": f"'{display_word}' added to the live word cloud!"
        }, 201)

    def handle_delete_wordcloud(self, word_id):
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM word_cloud WHERE id = ?", (word_id,))
        conn.commit()
        conn.close()
        self.send_json({"success": True, "message": "Word removed."})

    # ----------------- Static Asset Serving -----------------

    def serve_static(self, path):
        """Sert les fichiers statiques du dossier public/ (HTML, CSS, JS, images)."""
        if path == "/" or not path:
            filename = "index.html"
        else:
            filename = path.split("?")[0].lstrip("/")

        # Nettoyage et sécurité contre le Directory Traversal
        filename = os.path.normpath(filename)
        if filename.startswith(".."):
            self.send_response(403)
            self.end_headers()
            return

        # Cherche d'abord dans PUBLIC_DIR (public/), puis dans BASE_DIR en secours
        filepath = os.path.join(PUBLIC_DIR, filename)
        if not os.path.exists(filepath):
            filepath = os.path.join(BASE_DIR, filename)

        if not os.path.exists(filepath) or os.path.isdir(filepath):
            self.send_response(404)
            self.end_headers()
            return

        mime_type, _ = mimetypes.guess_type(filepath)
        mime_type = mime_type or "application/octet-stream"

        try:
            with open(filepath, "rb") as f:
                content = f.read()

            self.send_response(200)
            self.send_header("Content-Type", mime_type)
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            print(f"Erreur lors de la lecture de {filepath} : {e}")
            self.send_response(500)
            self.end_headers()

def run_server(port=PORT):
    init_db()
    os.makedirs(PUBLIC_DIR, exist_ok=True)
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", port), CinemaRequestHandler) as httpd:
        print(f"🎬 Student Cinema Server running at http://localhost:{port}")
        print(f"🔑 Admin PIN is set to '{ADMIN_PIN}'")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down server.")

# ==============================================================================
# FONCTIONS GLOBALES (0 espace d'indentation, tout à gauche)
# ==============================================================================
#getting movie info from themoviedb.org

TMDB_API_KEY = "36714c952f9cd9e486626a91fd3d16fe"

def fetch_movie_from_tmdb(title):
    if not TMDB_API_KEY or TMDB_API_KEY == "TA_CLE_API_TMDB_ICI":
        return None

    try:
        query = urllib.parse.quote(title)
        url = f"https://api.themoviedb.org/3/search/movie?api_key={TMDB_API_KEY}&query={query}&language=fr-FR"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))
            results = data.get("results", [])
            
            if results:
                movie = results[0]
                poster_path = movie.get("poster_path")
                poster_url = f"https://image.tmdb.org/t/p/w500{poster_path}" if poster_path else None
                synopsis = movie.get("overview") or "Aucun synopsis disponible."
                
                release_date = movie.get("release_date", "")
                year = int(release_date.split("-")[0]) if release_date and len(release_date) >= 4 else None
                
                return {
                    "title": movie.get("title") or title,
                    "poster_url": poster_url,
                    "synopsis": synopsis,
                    "year": year,
                    "genre": "Films cultes",
                    "runtime": "2h 00m"
                }
    except Exception as e:
        print(f"Erreur TMDB pour '{title}' : {e}")
    
    return None


if __name__ == "__main__":
    import sys
    port = PORT
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            pass
    run_server(port)