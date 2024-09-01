from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash # type: ignore
import sqlite3
from functools import wraps
from datetime import datetime,timedelta
import pytz # type: ignore

app = Flask(__name__, template_folder='templates')
app.secret_key = 'supersecretkey'

now = datetime.now()


tools = [
    {"name": "hammer", "photo_url": "/static/images/hammer.jpg"},
    {"name": "screwdriver", "photo_url": "/static/images/screwdriver.jpg"},
    {"name": "wrench", "photo_url": "/static/images/wrench.jpg"}
]

def init_db():
    with sqlite3.connect('tool.db') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                password TEXT NOT NULL,
                role TEXT NOT NULL
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tools (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tool_id TEXT NOT NULL,
                tool_name TEXT NOT NULL,
                status TEXT NOT NULL
            )
        ''')
        conn.commit()
    # Add initial users
    # with sqlite3.connect('tools.db') as conn:
    #     cursor = conn.cursor()
    #     cursor.execute("INSERT OR IGNORE INTO users (username, password, role) VALUES ('owner', 'ownerpass', 'owner')")
    #     cursor.execute("INSERT OR IGNORE INTO users (username, password, role) VALUES ('user', 'userpass', 'user')")
    #     conn.commit()

def login_required(role):
    def wrapper(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'logged_in' not in session or session['role'] != role:
                return redirect(url_for('login', role=role))
            return f(*args, **kwargs)
        return decorated_function
    return wrapper

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login/<role>', methods=['GET', 'POST'])
def login(role):
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        with sqlite3.connect('tools.db') as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM users WHERE username = ? AND password = ? AND role = ?', (username, password, role))
            user = cursor.fetchone()
            if user:
                session['logged_in'] = True
                session['username'] = user[1]
                session['role'] = user[3]
                username = session['username']
                if role == 'supervisor':
                    return redirect(url_for('supervisor_dashboard'))
                elif role == 'user':
                    return redirect(url_for('user_dashboard'))
                elif role == 'admin':
                    return redirect(url_for('admin_dashboard'))
            else:
                return "Invalid credentials"
    return render_template('login.html', role=role)

@app.route('/check_availability/<tool>/<quantity>')
def check_availability(tool, quantity):
    try:
        conn = sqlite3.connect('tools.db')
        cursor = conn.cursor()
        cursor.execute("SELECT quantity FROM tools WHERE name = ?", (tool,))
        row = cursor.fetchone()
        if row:
            available_quantity = row[0]
            if int(quantity) <= available_quantity:
                return jsonify({"available": True})
            else:
                return jsonify({"available": False})
        else:
            return jsonify({"available": False})
    except Exception as e:
        print("Error:", e)
        return jsonify({"available": False})
    finally:
        conn.close()

@app.route('/request_tools', methods=['POST'])
def request_tools():
    try:
        request_data = request.get_json()
        tools = request_data['tools']
        conn = sqlite3.connect('tools.db')
        cursor = conn.cursor()
        username = session.get('username')
        datetimex = now.strftime("%d/%m/%Y %H:%M:%S")
        for tool, quantity in tools.items():
            cursor.execute("INSERT INTO requests (tool_name, quantity,requested_by,date_time,status) VALUES (?,?,?,?,?)", (tool, quantity,username,datetimex,'-1'))
        conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        print("Error:", e)
        return jsonify({"success": False})
    finally:
        conn.close()

@app.route('/supervisor_dashboard')
def supervisor_dashboard():
    try:
       
        conn = sqlite3.connect('tools.db')
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM requests WHERE status = '-1'")
        requests = cursor.fetchall()
        username = session.get('username')
        return render_template('supervisor_dashboard.html', requests=requests,username=username)
    except Exception as e:
        print("Error:", e)
        return render_template('supervisor_dashboard.html', requests=[])
    finally:
        conn.close()


@app.route('/admin_dashboard')
def admin_dashboard():
    try:
       
        conn = sqlite3.connect('tools.db')
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM requests WHERE status = '1'")
        requests = cursor.fetchall()

        cursor.execute("SELECT * FROM requests WHERE status = '2'")
        requests2 = cursor.fetchall()

        cursor.execute("SELECT * FROM requests WHERE status = '3'")
        requests3 = cursor.fetchall()

        username = session.get('username')
        return render_template('admin_dashboard.html', requests=requests,requests2=requests2,requests3=requests3, username=username)
    except Exception as e:
        print("Error:", e)
        return render_template('admin_dashboard.html', requests=[])
    finally:
        conn.close()


def get_total_quantity(tool):
    try:
        conn = sqlite3.connect('tools.db')
        cursor = conn.cursor()
        cursor.execute("SELECT quantity FROM tools WHERE name = ?", (tool,))
        row = cursor.fetchone()
        if row:
            return row[0]
        else:
            return None
    except Exception as e:
        print("Error:", e)
        return None
    finally:
        conn.close()

@app.route('/issue_items/<int:request_id>', methods=['POST'])
def issue_items(request_id):
    try:
        conn = sqlite3.connect('tools.db')
        cursor = conn.cursor()
        quantity = int(request.form['quantity'])
        due_date = request.form['due_date']
        due_date2 = request.form['due_date']
        due_check = request.form['due_date'].strip()
        if not due_check:
            tz = pytz.timezone('Asia/Kolkata')  
            current_time = datetime.now(tz)
            default_due_date = current_time + timedelta(days=7)
            due_date = default_due_date.strftime("%d/%m/%Y")
        else:
            due_date = due_check
            current_time = datetime.now()
            due_date_obj = datetime.strptime(due_date, "%d/%m/%Y")
            if due_date_obj < current_time:
                flash(f"Due date {due_date} has already passed.")
                return redirect(url_for('admin_dashboard'))

        cursor.execute("SELECT tool_name FROM requests WHERE id = ?", (request_id,))
        row = cursor.fetchone()
        if not row:
            flash(f"Request with id {request_id} not found.")
            return redirect(url_for('admin_dashboard'))
        

        quantity = int(request.form['quantity'])

        tool = row[0]
        
        availability_response = check_availability(tool, quantity)
        if availability_response.get_json()['available'] == False:
            flash(f"Requested quantity of {tool} is not available.")
            return redirect(url_for('admin_dashboard'))


        tz = pytz.timezone('Asia/Kolkata')  
        gmt_time = datetime.now(tz)
        datetimex = gmt_time.strftime("%d/%m/%Y %H:%M:%S")

        total_quantity = get_total_quantity(tool)
        if total_quantity is not None:
            new_quantity = total_quantity - quantity
            cursor.execute("UPDATE tools SET quantity = ? WHERE name = ?", (new_quantity, tool,))
            conn.commit()

        cursor.execute("UPDATE requests SET status = ?, quantity = ?,due_date = ?, issued_at= ? WHERE id = ?", ('2',quantity,due_date,datetimex,request_id,))
        conn.commit()

        return redirect(url_for('admin_dashboard'))
    except Exception as e:
        print("Error:", e)
        return redirect(url_for('admin_dashboard'))
    finally:
        conn.close()

@app.route('/return_items/<int:request_id>', methods=['POST'])
def return_items(request_id):
    try:
        conn = sqlite3.connect('tools.db')
        cursor = conn.cursor()
        quantity2 = int(request.form['quantity'])
        print(quantity2)
        
        cursor.execute("SELECT quantity FROM requests WHERE id = ?", (request_id,))
        row2 = cursor.fetchone()
        if not row2:
            flash(f"Request with id {request_id} not found.")
            return redirect(url_for('admin_dashboard'))
        quantity = row2[0]
        # print(quantity)

        if quantity2 > quantity:
            flash(f"Returned quantity cannot be more than issued quantity.")
            return redirect(url_for('admin_dashboard'))
        

        cursor.execute("SELECT tool_name FROM requests WHERE id = ?", (request_id,))
        row = cursor.fetchone()
        if not row:
            flash(f"Request with id {request_id} not found.")
            return redirect(url_for('admin_dashboard'))
        tool = row[0]
        # print(tool)

        cursor.execute("SELECT quantity_returned FROM requests WHERE id = ?", (request_id,))
        row2 = cursor.fetchone()
        if not row2:
            flash(f"Request with id {request_id} not found.")
            return redirect(url_for('admin_dashboard'))
        quantity3 = row2[0]


        return_quantity = quantity3 + quantity2
        cursor.execute("UPDATE requests SET quantity_returned = ? WHERE id = ?", (return_quantity,request_id,))
        conn.commit()

        total_quantity = get_total_quantity(tool)
        if total_quantity is not None:
            new_quantity = total_quantity + quantity2
            cursor.execute("UPDATE tools SET quantity = ? WHERE name = ?", (new_quantity, tool,))
            conn.commit()


        if return_quantity == quantity:
            tz = pytz.timezone('Asia/Kolkata')  
            gmt_time = datetime.now(tz)
            datetimex = gmt_time.strftime("%d/%m/%Y %H:%M:%S")
            cursor.execute("UPDATE requests SET status = ?, returned_at = ? WHERE id = ?", ('3',datetimex,request_id,))
            conn.commit()

        return redirect(url_for('admin_dashboard'))
    except Exception as e:
        print("Error:", e)
        return redirect(url_for('admin_dashboard'))
    finally:
        conn.close()        

@app.route('/approve_request/<int:request_id>', methods=['POST'])
def approve_request(request_id):
    try:
        conn = sqlite3.connect('tools.db')
        cursor = conn.cursor()
        cursor.execute("UPDATE requests SET status = ? WHERE id = ?", ('1',request_id,))
        conn.commit()
        return redirect(url_for('supervisor_dashboard'))
    except Exception as e:
        print("Error:", e)
        return redirect(url_for('supervisor_dashboard'))
    finally:
        conn.close()

@app.route('/reject_request/<int:request_id>', methods=['POST'])
def reject_request(request_id):
    try:
        conn = sqlite3.connect('tools.db')
        cursor = conn.cursor()
        cursor.execute("UPDATE requests SET status = ? WHERE id = ?", ('0',request_id,))
        conn.commit()
        return redirect(url_for('supervisor_dashboard'))
    except Exception as e:
        print("Error:", e)
        return redirect(url_for('supervisor_dashboard'))
    finally:
        conn.close()


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))


@app.route('/user_dashboard')
@login_required('user')
def user_dashboard():
    username = session.get('username')
    return render_template('user_dashboard.html', username=username, tools=tools)

if __name__ == '__main__':
    init_db()
    app.run(debug=True,port=5000)
