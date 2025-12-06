# analyzers.py
from datetime import timedelta, datetime
from models import PriceRange, BlacklistCategory

class PurchaseAnalyzer:
    @staticmethod
    def analyze_impulse(user, price, category):
        """
        Анализ импульсивности покупки
        Смотрим на финансы юзера и решаем насколько рискованная покупка
        """
        
        # сначала проверяем blacklist
        is_blacklisted = BlacklistCategory.query.filter_by(
            user_id=user.id, 
            category=category
        ).first() is not None
        
        # ищем подходящий диапазон цен
        price_range = PriceRange.query.filter(
            PriceRange.user_id == user.id,
            PriceRange.min_price <= price,
            (PriceRange.max_price >= price) | (PriceRange.max_price.is_(None))
        ).order_by(PriceRange.min_price.desc()).first()
        
        cooling_days = price_range.cooling_days if price_range else 7
        
        # === ФИНАНСОВЫЙ АНАЛИЗ ===
        
        # 1. хватит ли денег?
        can_afford_now = price <= user.current_savings
        shortage = max(0, price - user.current_savings)
        
        # 2. через сколько накопим
        savings_days = 0
        savings_plan = None
        
        if user.use_savings_calculation and not can_afford_now and user.monthly_savings > 0:
            # сколько нужно накопить
            daily_savings = user.monthly_savings / 30
            savings_days = int(shortage / daily_savings) + 1
            
            # план накопления
            savings_plan = {
                'shortage': shortage,
                'daily_savings': daily_savings,
                'days_needed': savings_days,
                'target_date': (datetime.utcnow() + timedelta(days=savings_days)).strftime('%d.%m.%Y'),
                'monthly_impact': (price / user.salary * 100) if user.salary > 0 else 0
            }
        
        # 3. итоговый период ожидания
        # берём максимум из: период охлаждения, период накопления, доп период для крупных покупок
        
        extra_days = 0
        if price > user.salary * 0.5:  # если > 50% зарплаты
            extra_days = 14  # дополнительные 2 недели
        elif price > user.salary * 0.3:
            extra_days = 7
        
        total_cooling_days = max(cooling_days, savings_days) + extra_days
        
        # === РАСЧЁТ УРОВНЯ ИМПУЛЬСИВНОСТИ ===
        
        impulse_score = 0
        reasons = []
        financial_warnings = []
        
        # Фактор 1: Цена vs зарплата
        if user.salary > 0:
            price_ratio = (price / user.salary) * 100
            if price_ratio > 100:
                impulse_score += 50
                reasons.append(f"💰 Цена превышает месячную зарплату ({price_ratio:.0f}%)")
                financial_warnings.append("⚠️ Это очень крупная покупка, требующая особого внимания")
            elif price_ratio > 50:
                impulse_score += 40
                reasons.append(f"💰 Цена составляет {price_ratio:.0f}% от зарплаты")
                financial_warnings.append("⚠️ Покупка значительно повлияет на бюджет")
            elif price_ratio > 25:
                impulse_score += 25
                reasons.append(f"💸 Цена составляет {price_ratio:.0f}% от зарплаты")
            elif price_ratio > 10:
                impulse_score += 15
                reasons.append(f"💵 Цена составляет {price_ratio:.0f}% от зарплаты")
        
        # Фактор 2: Накопления
        if not can_afford_now:
            impulse_score += 35
            reasons.append(f"🏦 Недостаточно накоплений (нужно ещё {shortage:,.0f} ₽)")
            
            if savings_plan:
                if savings_days > 90:
                    financial_warnings.append(f"⏳ Потребуется {savings_days} дней накопления")
                    reasons.append(f"⏰ Более 3 месяцев на накопление")
                elif savings_days > 30:
                    financial_warnings.append(f"⏳ Потребуется около {savings_days} дней накопления")
                else:
                    financial_warnings.append(f"✅ Можно накопить за {savings_days} дней")
        
        elif price > user.current_savings * 0.8:
            impulse_score += 20
            reasons.append(f"⚠️ Покупка заберёт {(price/user.current_savings*100):.0f}% накоплений")
            financial_warnings.append("💰 После покупки останется мало средств на непредвиденные расходы")
        elif price > user.current_savings * 0.5:
            impulse_score += 10
            reasons.append(f"⚠️ Покупка заберёт {(price/user.current_savings*100):.0f}% накоплений")
        
        # Фактор 3: блэклист
        if is_blacklisted:
            impulse_score = 100
            reasons.append(f"🚫 Категория '{category}' в чёрном списке")
        
        # Фактор 4: подушка безопасности
        if user.current_savings > 0:
            ideal_cushion = user.salary * 3  # идеально 3-6 месяцев
            after_purchase = user.current_savings - price
            
            if after_purchase < user.salary:
                impulse_score += 15
                reasons.append("📉 После покупки подушка безопасности < 1 месяца")
                financial_warnings.append("⚠️ Рекомендуется иметь подушку минимум в 1 месячный доход")
        
        # === УРОВЕНЬ РИСКА ===
        
        if impulse_score >= 70:
            risk_level = 'high'
            emoji = '🔴'
            risk_description = 'Очень высокий риск'
        elif impulse_score >= 40:
            risk_level = 'medium'
            emoji = '🟡'
            risk_description = 'Средний риск'
        else:
            risk_level = 'low'
            emoji = '🟢'
            risk_description = 'Низкий риск'
        
        # === РЕКОМЕНДАЦИЯ ===
        
        if is_blacklisted:
            recommendation = 'Покупка запрещена вашими настройками'
            action_plan = 'Вы добавили эту категорию в чёрный список. Удалите её из настроек, если передумали.'
        
        elif not can_afford_now:
            if savings_plan:
                recommendation = f'Накопите ещё {shortage:,.0f} ₽ за {savings_days} дней'
                action_plan = (
                    f"📅 План накопления:\n"
                    f"• Откладывайте {savings_plan['daily_savings']:,.0f} ₽/день\n"
                    f"• Цель: {savings_plan['target_date']}\n"
                    f"• После накопления подождите ещё {cooling_days} дней охлаждения"
                )
            else:
                recommendation = f'Недостаточно средств (не хватает {shortage:,.0f} ₽)'
                action_plan = 'Настройте ежемесячные накопления в профиле для расчёта плана'
        
        elif total_cooling_days > 0:
            recommendation = f'Период обдумывания: {total_cooling_days} дней'
            
            parts = []
            if cooling_days > 0:
                parts.append(f"{cooling_days} дней охлаждения")
            if savings_days > 0:
                parts.append(f"{savings_days} дней накопления")
            if extra_days > 0:
                parts.append(f"{extra_days} дней на крупную покупку")
            
            action_plan = f"Подождите: {' + '.join(parts)}"
        
        else:
            recommendation = 'Можно совершить покупку сейчас'
            action_plan = 'У вас достаточно средств, покупка не критична для бюджета'
        
        # === ФИНАНСОВОЕ ЗДОРОВЬЕ ===
        
        financial_health = {
            'before': {
                'savings': user.current_savings,
                'savings_months': (user.current_savings / user.salary) if user.salary > 0 else 0
            },
            'after': {
                'savings': max(0, user.current_savings - price),
                'savings_months': max(0, (user.current_savings - price) / user.salary) if user.salary > 0 else 0
            },
            'impact': 'positive' if can_afford_now and price < user.current_savings * 0.3 else 'negative'
        }
        
        # === РЕЗУЛЬТАТ ===
        
        analysis = {
            # основное
            'is_blacklisted': is_blacklisted,
            'cooling_days': total_cooling_days,
            'price_cooling_days': cooling_days,
            'savings_days': savings_days,
            'extra_days': extra_days,
            
            # финансы
            'can_afford': can_afford_now,
            'shortage': shortage,
            'savings_plan': savings_plan,
            'financial_health': financial_health,
            
            # оценка риска
            'impulse_score': min(impulse_score, 100),
            'risk_level': risk_level,
            'risk_description': risk_description,
            'emoji': emoji,
            
            # рекомендации
            'recommendation': recommendation,
            'action_plan': action_plan,
            'reasons': reasons,
            'financial_warnings': financial_warnings,
            
            # доп инфо
            'price_to_salary_ratio': (price / user.salary * 100) if user.salary > 0 else 0,
            'ready_date': (datetime.utcnow() + timedelta(days=total_cooling_days)).strftime('%d.%m.%Y')
        }
        
        return analysis