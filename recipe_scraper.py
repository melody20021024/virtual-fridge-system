import requests
from bs4 import BeautifulSoup

def search_recipes(ingredients):
    query = '+'.join(ingredients)
    search_url = f"https://icook.tw/search/{query}"

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    response = requests.get(search_url, headers=headers)
    soup = BeautifulSoup(response.text, 'html.parser')

    cards = soup.select('li.browse-recipe-item')
    print(f"🧾 找到 {len(cards)} 筆資料")

    recipe_map = {}

    for card in cards[:30]:  # 多抓一些
        try:
            title = card.select_one('h2.browse-recipe-name').text.strip()
            ingredients_text = card.select_one('p.browse-recipe-content-ingredient').text.strip()
            link = "https://icook.tw" + card.select_one('a.browse-recipe-link')['href']

            img_tag = card.select_one('img.browse-recipe-cover-img')
            image = img_tag.get('data-src') or img_tag.get('src') or "https://via.placeholder.com/100x100?text=No+Image"

            # 計算命中幾個食材
            hit_count = sum(1 for keyword in ingredients if keyword in ingredients_text)

            if hit_count > 0:
                recipe_map[title] = {
                    "title": title,
                    "ingredients": ingredients_text,
                    "link": link,
                    "image": image,
                    "hits": hit_count
                }

        except Exception as e:
            print(f"❌ 錯誤略過：{e}")
            continue

    # 根據命中數量排序
    sorted_results = sorted(recipe_map.values(), key=lambda x: x['hits'], reverse=True)

    return sorted_results[:10]  # 最多回傳 10 筆

