from flask import Blueprint, render_template, request
from app.pipeline import run_pipeline

bp = Blueprint("main", __name__)


@bp.route("/", methods=["GET"])
def index():
    return render_template("index.html")


@bp.route("/analyse", methods=["POST"])
def analyse():
    pr_url = request.form.get("pr_url", "").strip()
    if not pr_url:
        return render_template("index.html", error="Please provide a PR URL.")

    context = run_pipeline(pr_url)
    return render_template("results.html", context=context)
