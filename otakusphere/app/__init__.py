from flask import Flask
from config import Config
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from datetime import datetime

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
login_manager.login_view = 'auth.login' # Tên blueprint.tên_hàm_view
login_manager.login_message = 'Vui lòng đăng nhập để truy cập trang này.'
login_manager.login_message_category = 'info'


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

    from app.models import User # Cần import sau khi db được khởi tạo để tránh circular import
    
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Đăng ký Blueprints
    from app.routes.auth_routes import bp as auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')

    from app.routes.user_routes import bp as user_bp
    app.register_blueprint(user_bp) # Không có prefix hoặc '/'

    from app.routes.admin_routes import bp as admin_bp
    app.register_blueprint(admin_bp, url_prefix='/admin')

    # Context processor để inject biến vào tất cả templates
    @app.context_processor
    def inject_current_user_role():
        from flask_login import current_user
        if current_user.is_authenticated:
            return dict(current_user_role=current_user.role)
        return dict(current_user_role=None)
    
    @app.context_processor
    def utility_processor():
        def get_current_year():
            return datetime.utcnow().year
        return dict(now=datetime.utcnow, get_current_year=get_current_year)

    return app