"""
Рациональный Ассистент
Главный файл приложения
"""

from flask import Flask, render_template
from flask_cors import CORS
import os

from models import db
from routes import api
#from notifications import NotificationScheduler


def create_app():
    app = Flask(__name__)
    
    # настройки
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv(
        'DATABASE_URL', 
        'sqlite:///rational_assistant.db'
    )
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key')
    
    # инициализация
    db.init_app(app)
    CORS(app)  # TODO: в продакшене надо настроить правильно
    
    # регистрируем роуты
    app.register_blueprint(api)
    
    # главная страница
    @app.route('/')
    def index():
        return render_template('index.html')
    
    @app.route('/health')
    def health():
        return {'status': 'ok', 'message': 'Рациональный Ассистент работает!'}
    
    return app


def init_db(app):
    """Инициализация БД"""
    with app.app_context():
        db.create_all()
        print("✅ База данных инициализирована!")


if __name__ == '__main__':
    app = create_app()
    init_db(app)
    
    # запускаем планировщик уведомлений
    # scheduler = NotificationScheduler(app)
    # scheduler.start()
    
    print("\n🎯 Рациональный Ассистент запущен!")
    print("📱 Откройте в браузере: http://localhost:5000")
    print("🔔 Планировщик уведомлений активен\n")
    
    app.run(debug=True, host='0.0.0.0', port=5000)