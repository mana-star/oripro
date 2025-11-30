from flask import Flask, render_template, request, redirect, url_for, session
from transformers import pipeline
import google.generativeai as genai
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin, login_user, logout_user, current_user, LoginManager, login_required

from flask_migrate import Migrate
from werkzeug.security import generate_password_hash, check_password_hash


# ChatGPTに聞いた
from dotenv import load_dotenv

# ChatGPTに聞いた
from datetime import timedelta

import os

# ✅ .envファイルを読み込む ChatGPTに聞いた
load_dotenv()

# ✅ Gemini設定
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

app = Flask(__name__)

app.secret_key = os.getenv("SECRET_KEY")

# ✅ 画像アップロード設定を追加 ChatGPTに聞いた
UPLOAD_FOLDER = "static/uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# ✅ DB設定
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("SQLALCHEMY_DATABASE_URI")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
# db = SQLAlchemy(app) のすぐ下あたりに追加 ChatGPTに聞いた
migrate = Migrate(app, db)

# ✅ Flask-Login設定
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

# ✅ Gemini設定
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# ✅ モデルロード（あなたの指定に変更）
sentiment_analyzer = pipeline(
    "sentiment-analysis",
    model="jarvisx17/japanese-sentiment-analysis"
)

# ==========================================
# DBモデル定義
# ==========================================
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    posts = db.relationship("Post", backref="author")
    background_color = db.Column(db.String(20), default="#ffffff")  # ←★ここを追加！
    button_color = db.Column(db.String(20), default="#2589d0")

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=True)
    transformed = db.Column(db.Text)
    label = db.Column(db.String(50))
    score = db.Column(db.Float)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    # ✅ ここを追加！
    image_filename = db.Column(db.String(255), nullable=True)
    
    # ✅ 追加：投稿日時 ChatGPTに聞いた
    created_at = db.Column(db.DateTime, default=db.func.now())

    # ChatGPTに聞いた
    @property
    def jst_created_at(self):
        # UTCからJSTに変換
        return self.created_at + timedelta(hours=9)


# ==========================================
# ログイン管理
# ==========================================
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ==========================================
# ルーティング
# ==========================================

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        text = request.form["user_text"]

        # 感情分析
        result = sentiment_analyzer(text)[0]
        label = result["label"]
        score = result["score"]
        transformed_text = text

        # ネガティブ判定
        if "NEG" in label or "negative" in label.lower():
            model = genai.GenerativeModel(model_name="gemini-2.5-flash")
            prompt = f"""
            以下の文を柔らかく、優しい言葉に変換してください。
            ただし、「はい、承知いたしました。」「はい、かしこまりました。」などの
            定型的なあいづち・敬語の応答は一切出力しないでください。
            変換後の文のみを返してください。

            入力文：
            {text}
            """

            response = model.generate_content([prompt])
            transformed_text = response.text.strip()

        # ✅ ログイン中なら投稿をDB保存
        if current_user.is_authenticated:
            new_post = Post(
                text=text,
                transformed=transformed_text,
                label=label,
                score=score,
                author=current_user
            )
            db.session.add(new_post)
            db.session.commit()

        return render_template(
            "result.html",
            original_text=text,
            transformed_text=transformed_text,
            label=label,
            score=round(score, 3)
        )

    return render_template("index.html")


# ==========================================
# ✅ ユーザー登録
# ==========================================
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        
        if User.query.filter_by(username=username).first():
            return "このユーザー名は既に使われています"
        
        new_user = User(username=username, password=password)
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for("login"))
    return render_template("register.html")


# ==========================================
# ✅ ログイン
# ==========================================
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        user = User.query.filter_by(username=username, password=password).first()
        if user:
            login_user(user)
            return redirect(url_for("mypage"))
        return "ログイン失敗"
    return render_template("login.html")


# ==========================================
# ✅ マイページ
# ==========================================
@app.route("/mypage")
@login_required
def mypage():
    # クエリパラメータで順序を取得（デフォルトは新しい→古い）ChatGPTに聞いた
    order = request.args.get("order", "desc")

    if order == "asc":
        posts = Post.query.filter_by(user_id=current_user.id).order_by(Post.created_at.asc()).all()
    else:
        posts = Post.query.filter_by(user_id=current_user.id).order_by(Post.created_at.desc()).all()

    return render_template("mypage.html", posts=posts, user=current_user, order=order)
    # posts = Post.query.filter_by(user_id=current_user.id).all()
    # return render_template("mypage.html", posts=posts, user=current_user)




# ==========================================
# ✅ ログアウト
# ==========================================
@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("index"))


# ==========================================
# ✅ 投稿ページ 
# ==========================================
@app.route("/post", methods=["GET", "POST"])
@login_required
def post():
    if request.method == "POST":
        text = request.form.get("text", "")
        image = request.files.get("image")

        # どちらも空ならエラー
        if not text and not image:
            return "テキストか画像のどちらかは必要です", 400
        label = score = transformed_text = None
        if text:
        # 感情分析
            result = sentiment_analyzer(text)[0]
            label = result["label"]
            score = result["score"]
            transformed_text = text

        # ネガティブならGeminiで変換
            if "NEG" in label or "negative" in label.lower():
                model = genai.GenerativeModel(model_name="gemini-2.5-flash")
                prompt = f"""
                以下の文を優しい言葉に書き換えてください。
                ただし、「はい、承知いたしました。」「はい、かしこまりました。」などの
                定型的なあいづちは絶対に出力しないでください。
                出力は変換後の文のみとしてください。

                入力文：
                {text}
                """
                response = model.generate_content([prompt])
                transformed_text = response.text.strip()
        
        # ✅ 画像があれば保存
        image_filename = None
        if image and image.filename:
            from werkzeug.utils import secure_filename
            filename = secure_filename(image.filename)
            image.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
            image_filename = filename
        
        # DBに保存
        new_post = Post(
            text=text,
            transformed=transformed_text,
            label=label,
            score=score,
            image_filename=image_filename,  # ←ここ追加
            author=current_user
        )
        db.session.add(new_post)
        db.session.commit()

        return redirect(url_for("mypage"))

    return render_template("post.html", user=current_user)

# ==========================================
# ✅ 非同期投稿用ルート（post.html JSから呼ばれる ChatGPTに聞いた
# ==========================================
@app.route("/post_async", methods=["POST"])
@login_required
def post_async():
    text = request.form.get("text", "")
    image = request.files.get("image")  # ✅ 画像を取得 ChatGPTに聞いた

    # どちらも空ならエラー
    if not text and not image:
            return "テキストか画像のどちらかは必要です", 400
    label = score = transformed_text = None

    if text:
    # 感情分析
        result = sentiment_analyzer(text)[0]
        label = result["label"]
        score = result["score"]
        transformed_text = text

        # ネガティブならGeminiで変換
        if "NEG" in label or "negative" in label.lower():
            model = genai.GenerativeModel(model_name="gemini-2.5-flash")
            prompt = f"""
            以下の文を優しい言葉に書き換えてください。
            ただし、「はい、承知いたしました。」「はい、かしこまりました。」などの
            定型的なあいづちは絶対に出力しないでください。
            出力は変換後の文のみとしてください。

            入力文：
            {text}
            """
            response = model.generate_content([prompt])
            transformed_text = response.text.strip()

    # ✅ 画像があれば保存 ChatGPTに聞いた
    image_filename = None
    if image and image.filename:
        from werkzeug.utils import secure_filename
        filename = secure_filename(image.filename)
        image.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
        image_filename = filename
    
    # DBに保存
    new_post = Post(
        text=text,
        transformed=transformed_text,
        label=label,
        score=score,
        image_filename=image_filename,  # ←追加
        author=current_user
    )
    db.session.add(new_post)
    db.session.commit()

    # JSONで返す（必要なら）
    return {"status": "success", "transformed": transformed_text}


# ==========================================
# ✅ 投稿削除 ChatGPTに聞いた
# ==========================================
@app.route("/post/delete/<int:post_id>", methods=["POST"])
@login_required
def delete_post(post_id):
    post = Post.query.get_or_404(post_id)
    # 自分の投稿以外は削除不可
    if post.user_id != current_user.id:
        return "権限がありません"
    db.session.delete(post)
    db.session.commit()
    return redirect(url_for("mypage"))


# ==========================================
# ✅ 投稿編集ページ表示 & 更新 ChatGPTに聞いた
# ==========================================
@app.route("/post/edit/<int:post_id>", methods=["GET", "POST"])
@login_required
def edit_post(post_id):
    post = Post.query.get_or_404(post_id)
    # 自分の投稿以外は編集不可
    if post.user_id != current_user.id:
        return "権限がありません"

    if request.method == "POST":
        new_text = request.form["text"]
        post.text = new_text

    # ---------------------------
    # 1️⃣ 画像削除処理追加
    # ---------------------------
    # if "delete_image" in request.form and post.image_filename:
    if request.form.get("delete_image") and post.image_filename:
        try:
            os.remove(os.path.join(app.config["UPLOAD_FOLDER"], post.image_filename))
        except FileNotFoundError:
            pass
        post.image_filename = None

    # ---------------------------
    # 2️⃣ 新しい画像アップロード処理追加
    # ---------------------------
    image = request.files.get("image")
    if image and image.filename:
        from werkzeug.utils import secure_filename
        filename = secure_filename(image.filename)
        image.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
        post.image_filename = filename

        # 感情分析と変換を再実行
        result = sentiment_analyzer(new_text)[0]
        post.label = result["label"]
        post.score = result["score"]
        post.transformed = new_text

        # ネガティブ判定で Gemini 変換
        if "NEG" in post.label or "negative" in post.label.lower():
            model = genai.GenerativeModel(model_name="gemini-2.5-flash")
            prompt = f"以下の文を柔らかく、優しい言葉に変換してください：\n{new_text}"
            response = model.generate_content(prompt)
            post.transformed = response.text.strip()

        db.session.commit()
        return redirect(url_for("mypage"))

    return render_template("edit_post.html", post=post)


# ==========================================
# ✅ 他ユーザー投稿一覧ページ ChatGPTに聞いた
# ==========================================
@app.route("/all_posts")
@login_required
def all_posts():
    # 自分の投稿も含める場合はこのまま、除外したい場合は .filter(Post.user_id != current_user.id)
    posts = Post.query.order_by(Post.created_at.desc()).all()
    return render_template("all_posts.html", posts=posts, user=current_user)

# ==========================================
# アカウント設定ページ表示 ChatGPTに聞いた
# ==========================================
@app.route("/account_settings")
@login_required
def account_settings():
    if request.method == 'POST':
        background_color = request.form.get('background_color')
        current_user.background_color = background_color
        db.session.commit()
        flash("設定を保存しました。", "success")
        return redirect(url_for('mypage'))
    
    return render_template("account_settings.html", user=current_user)


# アカウント更新処理
@app.route("/update_account", methods=["POST"])
@login_required
def update_account():
    new_username = request.form["username"]
    new_password = request.form["password"]
    new_background_color = request.form.get("background_color", "#ffffff")
    new_button_color = request.form.get("button_color", "#2589d0")  # デフォルトは任意の色

    
    # ユーザー名重複チェック
    existing_user = User.query.filter_by(username=new_username).first()
    if existing_user and existing_user.id != current_user.id:
        return "そのユーザー名はすでに使われています"

    # 更新
    current_user.username = new_username
    # current_user.password = new_password
    if new_password:
        current_user.password = new_password
    current_user.background_color = new_background_color
    current_user.button_color = new_button_color 
    db.session.commit()

    return redirect(url_for("mypage"))




if __name__ == "__main__":
    app.run(debug=True)
