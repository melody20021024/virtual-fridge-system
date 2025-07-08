from flask import Flask, render_template, request, redirect, session, flash
import sqlite3
import os
from datetime import datetime, timedelta
from recipe_scraper import search_recipes  # 這是你的爬蟲程式
from flask import session

app = Flask(__name__)
app.secret_key = '0000'

DB_PATH = 'fridge.db'

@app.route('/')
def home():
    return redirect('/welcome')

@app.route('/cinema')
def cinema_home():
    return render_template('cinema_home.html')

@app.route('/fridge')
def fridge_home():
    return redirect('/welcome')

@app.route('/welcome')
def welcome():
    return render_template('welcome.html')

@app.route('/index')
def index():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # 清除數量 <= 0 的食材
    cursor.execute("DELETE FROM fridge WHERE quantity IS NOT NULL AND CAST(quantity AS FLOAT) <= 0")
    cursor.execute("SELECT id, name, category, quantity, expiry_date FROM fridge")
    items = cursor.fetchall()

    # 分類整理，只保留數量 > 0 的食材
    categorized = {
        '肉類': [],
        '海鮮': [],
        '蔬菜': [],
        '調味料': [],
        '其他': []
    }
    for item in items:
        try:
            if float(item[3]) > 0:  # item[3] 是 quantity
                categorized[item[2]].append(item)  # item[2] 是 category
        except:
            pass  # 若 quantity 不是數字就跳過

    # 即期食材查找
    today = datetime.today().date()
    limit = today + timedelta(days=3)
    cursor.execute("SELECT name FROM fridge WHERE expiry_date IS NOT NULL AND expiry_date <= ? AND quantity > 0", (limit,))
    near_expiry = [row[0] for row in cursor.fetchall()]

    conn.close()

    return render_template('index.html', categorized=categorized, near_expiry=near_expiry)



@app.route('/add', methods=['POST'])
def add_item():
    name = request.form['name']
    category = request.form['category']
    quantity = request.form['quantity']
    expiry = request.form['expiry']

    # 數量轉為浮點數，若無法轉換則預設為 0
    try:
        quantity = float(quantity)
    except ValueError:
        quantity = 0.0

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO fridge (name, category, quantity, expiry_date) VALUES (?, ?, ?, ?)",
                   (name, category, quantity, expiry))
    conn.commit()
    conn.close()

    return redirect('/index')


def get_near_expiry_ingredients(days=3):
    today = datetime.today().date()
    limit = today + timedelta(days=days)

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT name, quantity FROM fridge 
        WHERE expiry_date IS NOT NULL 
        AND expiry_date <= ?
    """, (limit,))
    raw_results = c.fetchall()
    conn.close()

    # 過濾數量 <= 0 或轉換錯誤的項目
    results = []
    for name, qty in raw_results:
        try:
            if float(qty) > 0:
                results.append(name)
        except:
            continue
    return results



@app.route('/recommend', methods=['POST','GET'])
def recommend():
    near_expiry_ingredients = get_near_expiry_ingredients()
    
    if not near_expiry_ingredients:
        return redirect('/select')

    recipes = search_recipes(near_expiry_ingredients)
    return render_template('recommend.html', recipes=recipes)

@app.route('/select', methods=['GET', 'POST'])
def select_ingredients():
    if request.method == 'POST':
        selected = request.form.getlist('ingredients')
        if not selected:
            return "❗請至少選一個食材"

        recipes = search_recipes(selected)
        return render_template('recommend.html', recipes=recipes)

    # GET：顯示分類後的食材
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT name, category FROM fridge WHERE quantity IS NULL OR CAST(quantity AS FLOAT) > 0")
    rows = cursor.fetchall()
    conn.close()

    # 建立分類字典
    categorized = {
        "肉類": [],
        "海鮮": [],
        "蔬菜": [],
        "調味料": [],
        "其他": []
    }

    for name, category in rows:
        if category in categorized:
            categorized[category].append(name)
        else:
            categorized["其他"].append(name)

    return render_template('select.html', categorized=categorized)

@app.route('/delete/<int:item_id>', methods=['POST'])
def delete_item(item_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM fridge WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()
    return redirect('/index')

@app.route('/confirm_missing', methods=['POST'])
def confirm_missing():
    # 接收 checkbox 中使用者保留的缺料
    updated_missing = request.form.getlist('missing')  # 勾選的會進來
    session['missing_ingredients'] = updated_missing

    print("✅ 最後確認的缺料清單：", updated_missing)  # 可觀察確認是否正確
    return redirect('/show_recipe')


@app.route('/update_quantity')
def update_quantity():
    ingredients = session.get('recipe_ingredients', [])
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT name, quantity FROM fridge")
    fridge_data = {row[0]: row[1] for row in cursor.fetchall()}
    conn.close()

    matched = []
    for ing in ingredients:
        match = None
        for fridge_item in fridge_data:
            if fridge_item in ing or ing in fridge_item:
                match = fridge_item
                break
        if match:
            matched.append({'name': match, 'quantity': fridge_data[match]})

    return render_template('update_quantity.html', matched=matched)

@app.route('/apply_update', methods=['POST'])
def apply_update():
    updates = []
    for key in request.form:
        if key.startswith('mode_'):
            name = key.replace('mode_', '')
            mode = request.form[key]
            amount = request.form.get(f'value_{name}', '').strip()
            if amount:
                updates.append((name, mode, amount))

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    for name, mode, value in updates:
        try:
            val = float(value)
            if mode == 'used':
                cursor.execute("SELECT quantity FROM fridge WHERE name = ?", (name,))
                row = cursor.fetchone()
                if row:
                    current = float(row[0])
                    new_val = max(current - val, 0)
                    if new_val <= 0:
                        cursor.execute("DELETE FROM fridge WHERE name = ?", (name,))
                    else:
                        cursor.execute("UPDATE fridge SET quantity = ? WHERE name = ?", (new_val, name))
            elif mode == 'left':
                cursor.execute("UPDATE fridge SET quantity = ? WHERE name = ?", (val, name))
        except ValueError:
            continue

    # 清除數量小於等於 0 的食材
    cursor.execute("DELETE FROM fridge WHERE quantity <= 0")

    conn.commit()
    conn.close()

    return redirect('/index')


@app.route('/use_ingredients', methods=['POST'])
def use_ingredients():
    used = {key.replace('used_', ''): request.form[key] for key in request.form if key.startswith('used_')}
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    for name, used_qty in used.items():
        cursor.execute("SELECT quantity FROM fridge WHERE name = ?", (name,))
        row = cursor.fetchone()
        if row:
            current = row[0]
            try:
                left = float(current) - float(used_qty)
                if left <= 0:
                    cursor.execute("DELETE FROM fridge WHERE name = ?", (name,))
                else:
                    cursor.execute("UPDATE fridge SET quantity = ? WHERE name = ?", (str(left), name))
            except:
                pass

    # 清除數量小於等於 0 的食材
    cursor.execute("DELETE FROM fridge WHERE quantity <= 0")
    conn.commit()
    conn.close()
    return redirect('/index')

@app.route('/choose_recipe', methods=['POST'])
def choose_recipe():
    recipe = {
        'title': request.form['title'],
        'ingredients': request.form['ingredients'],
        'link': request.form['link'],
        'image': request.form['image']
    }
    session['selected_recipe'] = recipe

    # 撈冰箱食材
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM fridge")
    fridge_items = [row[0] for row in cursor.fetchall()]
    conn.close()

    # 比對哪些材料缺
    recipe_ingredients = [x.strip() for x in recipe['ingredients'].split('、')]
    missing = [item for item in recipe_ingredients if not any(f in item or item in f for f in fridge_items)]

    session['recipe_ingredients'] = recipe_ingredients
    session['missing_ingredients'] = missing

    return render_template('confirm_missing.html', missing=missing)

@app.route('/show_recipe')
def show_recipe():
    recipe = session.get('selected_recipe')  # 從 session 抓你在 choose_recipe() 存的資料

    if not recipe:
        return redirect('/index')  # 若沒有資料就跳回首頁避免出錯

    return render_template('show_recipe.html', recipe=recipe)  # ✅ 傳給前端 template 用



if __name__ == '__main__':
    app.run(debug=True, port=5000)
