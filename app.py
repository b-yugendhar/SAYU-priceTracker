import os
import logging
import io, csv
from flask import Flask, request, jsonify, render_template, redirect, url_for, flash, Response
from flask_login import LoginManager, login_required, current_user
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from config import Config
from db import db, init_db
from models import User, TrackedItem, PriceHistory
from auth import auth_bp
from scrapers import scrape_product
from scheduler import start_scheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config.from_object(Config)

# Configure API Rate Limiter
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"
)

# Register Blueprints
app.register_blueprint(auth_bp)

# Configure Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'
login_manager.login_message_category = 'error'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- Routing ---

@app.route("/")
def home():
    return render_template("home1.html")

@app.route("/track-page", methods=["GET", "POST"])
def track_page():
    if request.method == "GET":
        return render_template("track.html")

    if not current_user.is_authenticated:
        return jsonify({"error": "You must be logged in to track prices."}), 401

    data = request.json
    url = data.get("url")
    target_value = data.get("price")
    alert_mode = data.get("mode", "absolute")

    if not url or not target_value:
        return jsonify({"error": "Missing required fields"}), 400

    try:
        target_value = float(target_value)
    except ValueError:
        return jsonify({"error": "Invalid target value"}), 400

    logger.info(f"User {current_user.email} looking up {url} to track.")
    scraped_data = scrape_product(url)
    
    if not scraped_data or scraped_data.get('error') or scraped_data.get('price') is None:
        return jsonify({"error": "Could not extract current price from the provided URL."}), 500

    current_price = scraped_data['price']
    product_name = scraped_data['name']
    image_url = scraped_data.get('image_url', '')

    try:
        new_item = TrackedItem(
            user_id=current_user.id,
            url=url,
            platform='auto',
            product_name=product_name,
            image_url=image_url,
            alert_mode=alert_mode,
            alert_target=target_value,
            initial_price=current_price,
            current_price=current_price,
            lowest_price=current_price,
            highest_price=current_price
        )
        db.session.add(new_item)
        db.session.commit()
        
        # Log initial price to history
        new_history = PriceHistory(item_id=new_item.id, price=current_price)
        db.session.add(new_history)
        db.session.commit()

        return jsonify({
            "message": "Product tracking started successfully!", 
            "product_name": product_name, 
            "current_price": current_price
        })

    except Exception as e:
        db.session.rollback()
        logger.error(f"Database Insert Error on track_page POST: {e}")
        return jsonify({"error": "Failed to save tracking request"}), 500

@app.route("/p-details", methods=["GET", "POST"])
def p_details():
    if request.method == "GET":
        return render_template("pdetails.html")

    data = request.json
    url = data.get("productURL")

    if not url:
        return jsonify({"error": "No URL provided."}), 400

    scraped_data = scrape_product(url)
    if scraped_data and not scraped_data.get("error"):
        return jsonify(scraped_data)
    return jsonify({"error": scraped_data.get("error", "Failed to fetch product details.")}), 500

@app.route("/dashboard")
@login_required
def dashboard():
    items = TrackedItem.query.filter_by(user_id=current_user.id).order_by(TrackedItem.created_at.desc()).all()
    return render_template("dashboard.html", items=items)

# --- REST API Controls ---

@app.route("/api/items/<int:item_id>/pause", methods=["PATCH"])
@login_required
def pause_item(item_id):
    item = TrackedItem.query.filter_by(id=item_id, user_id=current_user.id).first()
    if item:
        item.status = 'paused'
        db.session.commit()
        return jsonify({"status": "success", "message": "Tracker paused."})
    return jsonify({"error": "Not Found"}), 404

@app.route("/api/items/<int:item_id>/resume", methods=["PATCH"])
@login_required
def resume_item(item_id):
    item = TrackedItem.query.filter_by(id=item_id, user_id=current_user.id).first()
    if item:
        item.status = 'active'
        item.consecutive_errors = 0
        db.session.commit()
        return jsonify({"status": "success", "message": "Tracker resumed."})
    return jsonify({"error": "Not Found"}), 404

@app.route("/api/items/<int:item_id>", methods=["DELETE"])
@login_required
def delete_item(item_id):
    item = TrackedItem.query.filter_by(id=item_id, user_id=current_user.id).first()
    if item:
        db.session.delete(item)
        db.session.commit()
        return jsonify({"status": "success", "message": "Tracker deleted."})
    return jsonify({"error": "Not Found"}), 404

@app.route("/api/items/<int:item_id>/history", methods=["GET"])
@login_required
def get_item_history(item_id):
    item = TrackedItem.query.filter_by(id=item_id, user_id=current_user.id).first()
    if not item:
        return jsonify({"error": "Unauthorized"}), 403

    history = PriceHistory.query.filter_by(item_id=item_id).order_by(PriceHistory.checked_at.asc()).all()
    result = [{"price": r.price, "date": r.checked_at} for r in history]
    return jsonify(result)

@app.route("/api/items/<int:item_id>/history.csv", methods=["GET"])
@login_required
def get_item_history_csv(item_id):
    item = TrackedItem.query.filter_by(id=item_id, user_id=current_user.id).first()
    if not item:
        return jsonify({"error": "Unauthorized"}), 403
        
    history = PriceHistory.query.filter_by(item_id=item_id).order_by(PriceHistory.checked_at.asc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Date Checked", "Price (INR)"])
    for row in history:
        writer.writerow([row.checked_at, row.price])

    return Response(output.getvalue(), mimetype="text/csv", headers={"Content-Disposition": f"attachment;filename=history_{item_id}.csv"})

@app.route("/unsubscribe/<int:item_id>", methods=["GET"])
def unsubscribe(item_id):
    item = TrackedItem.query.get(item_id)
    if item:
        item.status = 'paused'
        db.session.commit()
        return "<h3>Successfully Unsubscribed</h3><p>Your price tracker has been paused. You can resume it from your dashboard.</p>"
    return "Not Found", 404

@app.route("/health")
def health_check():
    return jsonify({"status": "healthy"})

# --- Initialization Core ---
init_db(app)

if __name__ == "__main__":
    # If we are running this file directly (local testing), start everything
    start_scheduler(app)
    app.run(debug=True)