"""
API Routes
"""

from flask import request, jsonify, Blueprint
from datetime import datetime, timedelta
from models import db, User, Purchase, PriceRange, BlacklistCategory, Notification
from parsers import ProductParser
from analyzers import PurchaseAnalyzer
import os

api = Blueprint('api', __name__, url_prefix='/api')


# ===== AUTH =====

@api.route('/auth/login', methods=['POST'])
def login():
    """Вход"""
    data = request.get_json()
    nickname = data.get('nickname', '').strip()
    
    if not nickname:
        return jsonify({'error': 'Никнейм обязателен'}), 400
    
    user = User.query.filter_by(nickname=nickname).first()
    
    if user:
        user.last_login = datetime.utcnow()
        db.session.commit()
        return jsonify({
            'message': 'Вход выполнен',
            'user': user.to_dict()
        })
    else:
        return jsonify({'error': 'Пользователь не найден'}), 404


@api.route('/auth/register', methods=['POST'])
def register():
    """Регистрация"""
    data = request.get_json()
    nickname = data.get('nickname', '').strip()
    
    if not nickname:
        return jsonify({'error': 'Никнейм обязателен'}), 400
    
    if User.query.filter_by(nickname=nickname).first():
        return jsonify({'error': 'Никнейм уже занят'}), 400
    
    # создаём юзера
    user = User(
        nickname=nickname,
        salary=float(data.get('salary', 100000)),
        monthly_savings=float(data.get('monthly_savings', 20000)),
        current_savings=float(data.get('current_savings', 0)),
        use_savings_calculation=data.get('use_savings_calculation', True)
    )
    
    db.session.add(user)
    
    # дефолтные диапазоны
    default_ranges = [
        PriceRange(user=user, min_price=0, max_price=15000, cooling_days=1),
        PriceRange(user=user, min_price=15000, max_price=50000, cooling_days=7),
        PriceRange(user=user, min_price=50000, max_price=100000, cooling_days=30),
        PriceRange(user=user, min_price=100000, max_price=None, cooling_days=90)
    ]
    db.session.add_all(default_ranges)
    
    db.session.commit()
    
    return jsonify({
        'message': 'Регистрация успешна',
        'user': user.to_dict()
    }), 201


# ===== ПАРСИНГ =====

@api.route('/parse-product', methods=['POST'])
def parse_product():
    """Парсинг товара"""
    data = request.get_json()
    url = data.get('url', '').strip()
    
    if not url:
        return jsonify({'error': 'URL обязателен'}), 400
    
    result = ProductParser.parse_product_url(url)
    
    if 'error' in result:
        return jsonify(result), 400
    
    return jsonify(result)


# ===== USERS =====

@api.route('/users/<int:user_id>', methods=['GET'])
def get_user(user_id):
    user = User.query.get_or_404(user_id)
    return jsonify(user.to_dict())


@api.route('/users/<int:user_id>', methods=['PUT'])
def update_user(user_id):
    """Обновление профиля"""
    user = User.query.get_or_404(user_id)
    data = request.get_json()
    
    # обновляем что пришло
    if 'salary' in data:
        user.salary = float(data['salary'])
    if 'monthly_savings' in data:
        user.monthly_savings = float(data['monthly_savings'])
    if 'current_savings' in data:
        user.current_savings = float(data['current_savings'])
    if 'use_savings_calculation' in data:
        user.use_savings_calculation = data['use_savings_calculation']
    if 'notification_interval' in data:
        user.notification_interval = data['notification_interval']
    if 'browser_notifications' in data:
        user.browser_notifications = data['browser_notifications']
    if 'telegram_notifications' in data:
        user.telegram_notifications = data['telegram_notifications']
    
    db.session.commit()
    return jsonify({'message': 'Пользователь обновлен', 'user': user.to_dict()})


# ===== ПОКУПКИ =====

@api.route('/purchases', methods=['GET'])
def get_purchases():
    """Список покупок"""
    user_id = request.args.get('user_id', type=int)
    status = request.args.get('status')
    
    if not user_id:
        return jsonify({'error': 'user_id обязателен'}), 400
    
    query = Purchase.query.filter_by(user_id=user_id)
    if status:
        query = query.filter_by(status=status)
    
    purchases = query.order_by(Purchase.created_at.desc()).all()
    return jsonify([p.to_dict() for p in purchases])


@api.route('/purchases', methods=['POST'])
def create_purchase():
    """Создание покупки с анализом"""
    data = request.get_json()
    
    # проверяем что всё есть
    if not all(k in data for k in ['user_id', 'name', 'price', 'category']):
        return jsonify({'error': 'user_id, name, price и category обязательны'}), 400
    
    user = User.query.get_or_404(data['user_id'])
    
    price = float(data['price'])
    category = data['category']
    
    # анализируем
    analysis = PurchaseAnalyzer.analyze_impulse(user, price, category)
    
    # дата окончания
    cooling_end_date = datetime.utcnow() + timedelta(days=analysis['cooling_days'])
    
    # создаём
    purchase = Purchase(
        user_id=data['user_id'],
        name=data['name'],
        price=price,
        category=category,
        cooling_period_days=analysis['cooling_days'],
        cooling_end_date=cooling_end_date,
        is_blacklisted=analysis['is_blacklisted'],
        notes=data.get('notes', ''),
        product_url=data.get('product_url'),
        image_url=data.get('image_url')
    )
    
    db.session.add(purchase)
    db.session.commit()
    
    return jsonify({
        'id': purchase.id,
        'purchase': purchase.to_dict(),
        'analysis': analysis
    }), 201


@api.route('/purchases/<int:purchase_id>', methods=['PUT'])
def update_purchase(purchase_id):
    """Обновление покупки"""
    purchase = Purchase.query.get_or_404(purchase_id)
    data = request.get_json()
    
    if 'status' in data:
        if data['status'] not in ['pending', 'approved', 'rejected']:
            return jsonify({'error': 'Неверный статус'}), 400
        purchase.status = data['status']
    
    if 'notes' in data:
        purchase.notes = data['notes']
    
    db.session.commit()
    return jsonify({'message': 'Покупка обновлена', 'purchase': purchase.to_dict()})


@api.route('/purchases/<int:purchase_id>', methods=['DELETE'])
def delete_purchase(purchase_id):
    """Удаление"""
    purchase = Purchase.query.get_or_404(purchase_id)
    db.session.delete(purchase)
    db.session.commit()
    return jsonify({'message': 'Покупка удалена'})


# ===== ДИАПАЗОНЫ ЦЕН =====

@api.route('/price-ranges/<int:user_id>', methods=['GET'])
def get_price_ranges(user_id):
    ranges = PriceRange.query.filter_by(user_id=user_id).order_by(PriceRange.min_price).all()
    return jsonify([r.to_dict() for r in ranges])


@api.route('/price-ranges', methods=['POST'])
def create_price_range():
    data = request.get_json()
    
    if not all(k in data for k in ['user_id', 'min_price', 'cooling_days']):
        return jsonify({'error': 'user_id, min_price и cooling_days обязательны'}), 400
    
    price_range = PriceRange(
        user_id=data['user_id'],
        min_price=float(data['min_price']),
        max_price=float(data['max_price']) if data.get('max_price') else None,
        cooling_days=int(data['cooling_days'])
    )
    
    db.session.add(price_range)
    db.session.commit()
    
    return jsonify({
        'message': 'Диапазон создан',
        'range': price_range.to_dict()
    }), 201


@api.route('/price-ranges/<int:range_id>', methods=['DELETE'])
def delete_price_range(range_id):
    price_range = PriceRange.query.get_or_404(range_id)
    db.session.delete(price_range)
    db.session.commit()
    return jsonify({'message': 'Диапазон удален'})


# ===== BLACKLIST =====

@api.route('/blacklist/<int:user_id>', methods=['GET'])
def get_blacklist(user_id):
    categories = BlacklistCategory.query.filter_by(user_id=user_id).all()
    return jsonify([c.to_dict() for c in categories])


@api.route('/blacklist', methods=['POST'])
def add_to_blacklist():
    data = request.get_json()
    
    if not all(k in data for k in ['user_id', 'category']):
        return jsonify({'error': 'user_id и category обязательны'}), 400
    
    # проверка на дубликат
    existing = BlacklistCategory.query.filter_by(
        user_id=data['user_id'],
        category=data['category']
    ).first()
    
    if existing:
        return jsonify({'error': 'Категория уже в чёрном списке'}), 400
    
    category = BlacklistCategory(
        user_id=data['user_id'],
        category=data['category']
    )
    
    db.session.add(category)
    db.session.commit()
    
    return jsonify({
        'message': 'Категория добавлена',
        'category': category.to_dict()
    }), 201


@api.route('/blacklist/<int:category_id>', methods=['DELETE'])
def remove_from_blacklist(category_id):
    category = BlacklistCategory.query.get_or_404(category_id)
    db.session.delete(category)
    db.session.commit()
    return jsonify({'message': 'Категория удалена'})


# ===== СТАТИСТИКА =====

@api.route('/statistics/<int:user_id>', methods=['GET'])
def get_statistics(user_id):
    user = User.query.get_or_404(user_id)
    
    total = Purchase.query.filter_by(user_id=user_id).count()
    pending = Purchase.query.filter_by(user_id=user_id, status='pending').count()
    approved = Purchase.query.filter_by(user_id=user_id, status='approved').count()
    rejected = Purchase.query.filter_by(user_id=user_id, status='rejected').count()
    
    # сколько потрачено
    spent = db.session.query(db.func.sum(Purchase.price)).filter_by(
        user_id=user_id, status='approved'
    ).scalar() or 0
    
    # сколько сэкономлено
    saved = db.session.query(db.func.sum(Purchase.price)).filter_by(
        user_id=user_id, status='rejected'
    ).scalar() or 0
    
    return jsonify({
        'total': total,
        'pending': pending,
        'approved': approved,
        'rejected': rejected,
        'total_spent': float(spent),
        'total_saved': float(saved),
        'current_savings': user.current_savings,
        'monthly_savings': user.monthly_savings,
        'salary': user.salary
    })


# ===== УВЕДОМЛЕНИЯ =====

#@api.route('/notifications/<int:user_id>', methods=['GET'])
#def get_notifications(user_id):
#    """История уведомлений"""
#    notifications = Notification.query.filter_by(user_id=user_id)\
#        .order_by(Notification.sent_at.desc())\
#        .limit(50)\
#        .all()
#    return jsonify([n.to_dict() for n in notifications])


#@api.route('/telegram/connect', methods=['POST'])
# def telegram_connect():
#     """Получить ссылку для подключения телеги"""
#     data = request.get_json()
#     user_id = data.get('user_id')
    
#     if not user_id:
#         return jsonify({'error': 'user_id обязателен'}), 400
    
#     user = User.query.get_or_404(user_id)
    
#     bot_username = os.getenv('TELEGRAM_BOT_USERNAME', 'your_bot')
#     telegram_url = f"https://t.me/{bot_username}?start={user.telegram_code}"
    
#     return jsonify({
#         'telegram_url': telegram_url,
#         'code': user.telegram_code,
#         'connected': bool(user.telegram_chat_id)
#     })


# @api.route('/telegram/disconnect', methods=['POST'])
# def telegram_disconnect():
#     """Отключить телегу"""
#     data = request.get_json()
#     user_id = data.get('user_id')
    
#     if not user_id:
#         return jsonify({'error': 'user_id обязателен'}), 400
    
#     user = User.query.get_or_404(user_id)
#     user.telegram_chat_id = None
#     user.telegram_notifications = False
#     db.session.commit()
    
#     return jsonify({'message': 'Telegram отключен'})


# @api.route('/telegram/webhook', methods=['POST'])
# def telegram_webhook():
#     """Webhook от телеграма"""
#     data = request.get_json()
#     result = handle_telegram_webhook(data)
#     return jsonify(result)