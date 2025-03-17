from flask import Flask, session, request, redirect, url_for, render_template
import sqlite3
import random
import os

app = Flask(__name__, static_folder='static')
app.secret_key = 'supersecretkeyidunno'

generic_profile_pics= []

def get_db_connection():
    conn = sqlite3.connect('users.db')
    conn.row_factory = sqlite3.Row
    return conn


def load_generic_profile_pics():
    profile_pics = []
    profile_pic_folder = os.path.join('static', 'profile_pics')

    for root, dirs, files in os.walk(profile_pic_folder):
        for file in files:
            if file.endswith(('jpg', 'jpeg', 'png')):
                profile_pics.append(file)

    return profile_pics


@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        return redirect(url_for('home'))

    user_id = get_user_id(session['username'])
    is_admin = is_user_admin(session['username'])

    followed_users = get_followed_users(user_id)

    if followed_users:
        posts = get_posts_from_followed_users(followed_users, is_admin)
    else:
        posts = get_random_posts_excluding_user(user_id, is_admin)

    existing_post_ids = {post['created_at'] for post in posts}

    if len(posts) < 5:
        additional_posts_needed = 5 - len(posts)
        additional_posts = get_random_posts_excluding_user(user_id, is_admin, limit=additional_posts_needed)

        for post in additional_posts:
            if post['created_at'] not in existing_post_ids:
                posts.append(post)
                existing_post_ids.add(post['created_at'])

    return render_template('dashboard.html', posts=posts, username=session['username'])


def get_random_posts_excluding_user(user_id, is_admin, limit=5):
    conn = get_db_connection()
    if is_admin:
        posts = conn.execute('''
            SELECT posts.id, posts.content, posts.title, users.username, posts.created_at, users.profile_pic, users.is_admin
            FROM posts
            JOIN users ON posts.user_id = users.id
            WHERE posts.user_id != ?
            ORDER BY users.is_admin DESC, RANDOM()
            LIMIT ?
        ''', (user_id, limit)).fetchall()
    else:
        posts = conn.execute('''
            SELECT posts.id, posts.content, posts.title, users.username, posts.created_at, users.profile_pic
            FROM posts
            JOIN users ON posts.user_id = users.id
            WHERE posts.user_id != ? AND users.is_admin = 0
            ORDER BY RANDOM()
            LIMIT ?
        ''', (user_id, limit)).fetchall()
    conn.close()
    return posts




def get_admin_posts_prioritized():
    conn = get_db_connection()

    # First, fetch admin posts
    admin_posts = conn.execute('''
        SELECT posts.content, posts.title, users.username, posts.created_at 
        FROM posts 
        JOIN users ON posts.user_id = users.id
        WHERE users.is_admin = 1
        ORDER BY RANDOM()
    ''').fetchall()

    user_posts = conn.execute('''
        SELECT posts.content, posts.title, users.username, posts.created_at 
        FROM posts 
        JOIN users ON posts.user_id = users.id
        WHERE users.is_admin = 0
        ORDER BY RANDOM()
    ''').fetchall()

    conn.close()

    all_posts = admin_posts + user_posts
    random.shuffle(all_posts)  # Shuffle posts to randomize their order
    return all_posts


@app.route('/create_post', methods=['GET', 'POST'])
def create_post():
    if 'username' not in session:
        return redirect(url_for('home'))

    if request.method == 'POST':
        user_id = get_user_id(session['username'])
        title = request.form['title']
        content = request.form['content']

        # Insert into the posts table (title and content)
        conn = get_db_connection()
        conn.execute('INSERT INTO posts (user_id, title, content) VALUES (?, ?, ?)', (user_id, title, content))
        conn.commit()
        conn.close()

        return redirect(url_for('dashboard'))

    return render_template('create_post.html')


@app.route('/profile')
def profile():
    if 'username' not in session:
        return redirect(url_for('home'))

    user_id = get_user_id(session['username'])
    if not user_id:
        return redirect(url_for('home'))

    conn = get_db_connection()
    posts = conn.execute('''
        SELECT posts.id, posts.content, posts.created_at, posts.title, users.username, users.profile_pic
        FROM posts
        JOIN users ON posts.user_id = users.id
        WHERE posts.user_id = ?
        ORDER BY posts.created_at DESC
    ''', (user_id,)).fetchall()

    user = conn.execute('''
        SELECT username, profile_pic FROM users WHERE id = ?
    ''', (user_id,)).fetchone()

    if user is None:
        return redirect(url_for('home'))  # Redirect if user is not found

    logged_in_user_id = get_user_id(session['username'])
    is_following = get_is_following(user_id, logged_in_user_id)

    conn.close()
    profile_pic = user['profile_pic']

    return render_template('profile.html',
                           username=session['username'],
                           posts=posts,
                           profile_picture=profile_pic,
                           is_following=is_following)


def get_is_following(user_id, logged_in_user_id):
    conn = get_db_connection()
    following = conn.execute('''
        SELECT 1 FROM followers 
        WHERE follower_id = ? AND followed_id = ?
    ''', (logged_in_user_id, user_id)).fetchone()
    conn.close()
    return following is not None


@app.route('/search', methods=['GET'])
def search():
    search_query = request.args.get('search')
    if not search_query:
        return redirect(url_for('dashboard'))
    is_admin = is_user_admin(session['username'])

    posts, users = search_posts_and_users(search_query, is_admin)
    return render_template('search_results.html', posts=posts, users=users)


def search_posts_and_users(query, is_admin):
    conn = get_db_connection()

    # Fetching posts along with the post author's profile picture
    posts = conn.execute('SELECT content, created_at, user_id, users.username, users.profile_pic FROM posts '
                         'JOIN users ON posts.user_id = users.id WHERE content LIKE ?', ('%' + query + '%',)).fetchall()

    if is_admin:
        users = conn.execute('SELECT id, username, profile_pic FROM users WHERE username LIKE ?', ('%' + query + '%',)).fetchall()
    else:
        users = conn.execute('SELECT id, username, profile_pic FROM users WHERE username LIKE ? AND is_admin = 0',
                             ('%' + query + '%',)).fetchall()

    conn.close()
    return posts, users


def is_user_admin(username):
    conn = get_db_connection()
    user = conn.execute('SELECT is_admin FROM users WHERE username = ?', (username,)).fetchone()
    conn.close()
    return user['is_admin'] if user else 0


def get_user_id(username):
    conn = get_db_connection()
    user = conn.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone()
    conn.close()
    return user['id'] if user else None

def get_followed_users(user_id):
    conn = get_db_connection()
    followed_users = conn.execute('SELECT followed_id FROM followers WHERE follower_id = ?', (user_id,)).fetchall()
    conn.close()
    return [f['followed_id'] for f in followed_users]


@app.route('/followers')
def followers():
    if 'username' not in session:
        return redirect(url_for('home'))

    user_id = get_user_id(session['username'])
    followed_users = get_followed_users(user_id)

    users = []
    if followed_users:
        conn = get_db_connection()
        users = conn.execute('SELECT username FROM users WHERE id IN (?)',
                             (",".join(map(str, followed_users)),)).fetchall()
        conn.close()

    return render_template('followers.html', users=users)


def get_posts_from_followed_users(followed_users, is_admin):
    conn = get_db_connection()
    if is_admin:
        posts = conn.execute('''
            SELECT posts.id, posts.content, posts.title, users.username, posts.created_at, users.profile_pic, users.is_admin
            FROM posts
            JOIN users ON posts.user_id = users.id
            WHERE posts.user_id IN ({}) 
            ORDER BY users.is_admin DESC, posts.created_at DESC
        '''.format(",".join(map(str, followed_users)))).fetchall()
    else:
        posts = conn.execute('''
            SELECT posts.id, posts.content, posts.title, users.username, posts.created_at, users.profile_pic
            FROM posts
            JOIN users ON posts.user_id = users.id
            WHERE posts.user_id IN ({}) AND users.is_admin = 0
            ORDER BY posts.created_at DESC
        '''.format(",".join(map(str, followed_users)))).fetchall()
    conn.close()
    return posts



@app.route('/post/<int:post_id>', methods=['GET', 'POST'])
def view_post(post_id):
    if 'username' not in session:
        return redirect(url_for('home'))

    # Get post details
    conn = get_db_connection()
    post = conn.execute('''
        SELECT posts.id, posts.title, posts.content, posts.created_at, users.username, users.profile_pic
        FROM posts
        JOIN users ON posts.user_id = users.id
        WHERE posts.id = ?
    ''', (post_id,)).fetchone()

    if not post:
        return redirect(url_for('dashboard'))  # Redirect if the post does not exist

    # Get all replies to the post (including nested replies)
    replies = conn.execute('''
        SELECT replies.id, replies.content, replies.created_at, users.username, users.profile_pic, replies.parent_reply_id
        FROM replies
        JOIN users ON replies.user_id = users.id
        WHERE replies.post_id = ?
        ORDER BY replies.created_at DESC
    ''', (post_id,)).fetchall()

    # Create a list to store nested replies for each reply
    nested_replies_map = {}

    # For each reply, get nested replies
    for reply in replies:
        nested_replies = get_nested_replies(reply['id'])
        nested_replies_map[reply['id']] = nested_replies

    # Handle new replies
    if request.method == 'POST':
        user_id = get_user_id(session['username'])
        content = request.form['content']
        parent_reply_id = request.form.get('parent_reply_id')  # Can be None if it's a direct reply to the post

        conn.execute('''
            INSERT INTO replies (post_id, user_id, content, parent_reply_id)
            VALUES (?, ?, ?, ?)
        ''', (post_id, user_id, content, parent_reply_id))
        conn.commit()
        conn.close()
        return redirect(url_for('view_post', post_id=post_id))  # Refresh the page to show the new reply

    conn.close()

    return render_template('post.html', post=post, replies=replies, nested_replies_map=nested_replies_map)



def get_nested_replies(reply_id):
    conn = get_db_connection()
    replies = conn.execute('''
        SELECT replies.id, replies.content, replies.created_at, users.username, users.profile_pic, replies.parent_reply_id
        FROM replies
        JOIN users ON replies.user_id = users.id
        WHERE replies.parent_reply_id = ?
        ORDER BY replies.created_at DESC
    ''', (reply_id,)).fetchall()
    conn.close()
    return replies


@app.route('/follow/<int:followed_id>', methods=['POST'])
def follow_user(followed_id):
    if 'username' not in session:
        return redirect(url_for('home'))

    user_id = get_user_id(session['username'])

    # Insert into followers table
    conn = get_db_connection()
    conn.execute('INSERT INTO followers (follower_id, followed_id) VALUES (?, ?)', (user_id, followed_id))
    conn.commit()
    conn.close()

    return redirect(url_for('dashboard'))

def get_random_posts():
    conn = get_db_connection()
    posts = conn.execute('SELECT posts.content, users.username, posts.created_at FROM posts JOIN users ON posts.user_id = users.id ORDER BY RANDOM() LIMIT 5').fetchall()
    conn.close()
    return posts

def init_db():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('DROP TABLE IF EXISTS users')
    c.execute('DROP TABLE IF EXISTS posts')
    c.execute('DROP TABLE IF EXISTS followers')
    c.execute('DROP TABLE IF EXISTS replies')

    c.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL,
                profile_pic TEXT,
                is_admin BOOLEAN DEFAULT 0
            )
        ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
        ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS followers (
            follower_id INTEGER,
            followed_id INTEGER,
            FOREIGN KEY(follower_id) REFERENCES users(id),
            FOREIGN KEY(followed_id) REFERENCES users(id),
            PRIMARY KEY(follower_id, followed_id)
        )
        ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS replies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            parent_reply_id INTEGER,  -- This is for nested replies
            FOREIGN KEY (post_id) REFERENCES posts(id),
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (parent_reply_id) REFERENCES replies(id)
        );
    ''')

    c.execute("INSERT INTO users (username, password, is_admin) VALUES ('admin', 'adminpassword', 1)",)
    conn.commit()
    conn.close()

def create_user(username, password):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE username = ?", (username,))
    user = c.fetchone()
    if user:
        raise ValueError("Username already exists")

    # If no user found, insert new user
    c.execute('INSERT INTO users (username, password, is_admin) VALUES (?, ?, ?)', (username, password, 0))
    conn.commit()
    conn.close()

@app.route('/create_account', methods=['GET', 'POST'])
def create_account():
    error_message = None  # Variable to hold the error message

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        try:
            create_user(username, password)  # Try to create the user
            session['username'] = username

            selected_profile_pic = random.choice(generic_profile_pics)

            conn = get_db_connection()
            conn.execute('UPDATE users SET profile_pic = ? WHERE username = ?', (selected_profile_pic, username))
            conn.commit()
            conn.close()

            return redirect(url_for('dashboard'))

        except ValueError as e:
            error_message = str(e)  # Catch the ValueError and store the error message

    return render_template('create_account.html', error_message=error_message)



@app.route('/sql_login', methods=['GET', 'POST'])
def sql_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = sqlite3.connect('users.db')
        c = conn.cursor()

        query = f"SELECT * FROM users WHERE username = '{username}' AND password = '{password}'"
        c.execute(query)
        user = c.fetchone()
        conn.close()

        if user:
            session['username'] = user[1]
            return redirect(url_for('dashboard'))
        else:
            return render_template('sql_login.html', error_message="Invalid Login Credentials")
    return render_template('sql_login.html')


@app.route('/osint_login', methods=['GET', 'POST'])
def osint_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = sqlite3.connect('users.db')
        c = conn.cursor()

        query = "SELECT * FROM users WHERE username = ? AND password = ?"
        c.execute(query, (username, password))

        user = c.fetchone()
        conn.close()

        if user:
            session['username'] = username
            return redirect(url_for('dashboard'))
        else:
            return render_template('osint_login.html', error_message="Invalid Login Credentials")
    return render_template('osint_login.html')


@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('home'))


@app.route('/')
def home():
    return render_template('home.html')



if __name__ == '__main__':
    init_db()
    generic_profile_pics = load_generic_profile_pics()
    app.run(debug=True)

