# parsers.py
import requests
from urllib.parse import urlparse

class ProductParser:
    @staticmethod
    def parse_product_url(url):
        """
        Парсинг товаров с Wildberries и Ozon
        TODO: добавить больше маркетплейсов (aliexpress, amazon?)
        """
        try:
            parsed_url = urlparse(url)
            domain = parsed_url.netloc.lower()

            if 'wildberries.ru' in domain or 'wb.ru' in domain:
                # WB парсинг
                # URL типа: /catalog/123456/detail.aspx
                path_parts = parsed_url.path.split('/')
                if 'catalog' in path_parts and len(path_parts) > 2:
                    product_id_str = path_parts[path_parts.index('catalog') + 1]
                    try:
                        product_id = int(product_id_str)
                    except ValueError:
                        return {'error': 'Неверный ID товара в URL'}
                else:
                    return {'error': 'Неверный формат URL Wildberries'}

                # запрос к API (dest=-1257786 это Москва, spp=30 для скидок)
                api_url = f'https://card.wb.ru/cards/v2/detail?appType=1&curr=rub&dest=-1257786&spp=30&nm={product_id}'
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Accept': 'application/json',
                    'Referer': 'https://www.wildberries.ru/'
                }
                response = requests.get(api_url, headers=headers, timeout=10)
                response.raise_for_status()
                data = response.json().get('data', {}).get('products', [])
                if not data:
                    return {'error': 'Товар не найден'}

                product = data[0]
                name = product.get('name', 'Неизвестно')
                price = product.get('salePriceU', 0) / 100  # в копейках
                category = product.get('subj_name', product.get('subj_root_name', 'Неизвестно'))

                # картинка (алгоритм корзины WB)
                vol = product_id // 100000
                part = product_id // 1000
                basket_num = (vol % 100) + 1
                basket = f'basket-{basket_num:02d}.wb.ru'
                image_url = f'https://{basket}/vol{vol}/part{part}/{product_id}/images/c516x688/1.jpg'

                return {
                    'name': name,
                    'price': price,
                    'category': category,
                    'image_url': image_url
                }

            elif 'ozon.ru' in domain:
                # Ozon парсинг (сложнее чем WB)
                path_parts = parsed_url.path.split('/')
                if 'product' in path_parts and len(path_parts) > 2:
                    product_slug = path_parts[path_parts.index('product') + 1]
                    # достаём ID из slug'а
                    try:
                        # иногда slug типа "name-123456"
                        product_id = int(product_slug.split('-')[-1]) if '-' in product_slug else int(product_slug)
                    except ValueError:
                        return {'error': 'Неверный ID товара в URL Ozon'}
                else:
                    return {'error': 'Неверный формат URL Ozon'}

                # API озона (v2, json)
                api_url = f'https://www.ozon.ru/api/composer-api.bx/page/json/v2?url=/product/{product_id}'
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Accept': 'application/json',
                    'Referer': 'https://www.ozon.ru/'
                }
                response = requests.get(api_url, headers=headers, timeout=10)
                response.raise_for_status()
                json_data = response.json()
                
                # ищем данные в widgetStates
                widgets = json_data.get('widgetStates', {})
                main_widget_key = next((k for k in widgets if 'webProductHeading' in k), None)
                if not main_widget_key:
                    return {'error': 'Данные товара не найдены в ответе Ozon'}

                main_data = widgets[main_widget_key]
                name = main_data.get('title', 'Неизвестно')

                # цена в отдельном виджете
                price_widget_key = next((k for k in widgets if 'webSale' in k), None)
                price_data = widgets.get(price_widget_key, {})
                price_str = price_data.get('price', '0 ₽').replace('₽', '').replace(' ', '').strip()
                price = float(price_str) if price_str.isdigit() else 0.0

                # категория из breadcrumbs
                category = 'Неизвестно'
                seo_widget_key = next((k for k in widgets if 'seoBreadcrumbs' in k), None)
                if seo_widget_key:
                    breadcrumbs = widgets[seo_widget_key].get('breadcrumbs', [])
                    # пропускаем первый (главная страница)
                    category = ' / '.join([b.get('name', '') for b in breadcrumbs[1:]])

                # картинка
                image_widget_key = next((k for k in widgets if 'webGallery' in k), None)
                image_data = widgets.get(image_widget_key, {}).get('images', [])
                image_url = image_data[0].get('src', None) if image_data else None
                if image_url and not image_url.startswith('http'):
                    image_url = 'https:' + image_url

                return {
                    'name': name,
                    'price': price,
                    'category': category,
                    'image_url': image_url
                }

            else:
                return {'error': 'Поддерживаются только Wildberries и Ozon'}

        except requests.RequestException as e:
            return {'error': f'Ошибка запроса: {str(e)}'}
        except ValueError as e:
            return {'error': f'Ошибка парсинга данных: {str(e)}'}
        except Exception as e:
            # на всякий случай
            return {'error': f'Неизвестная ошибка: {str(e)}'}