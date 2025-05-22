from flask import Flask, render_template, redirect, flash, url_for, request, session
from models import db, User, Post, Comment
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import func


app = Flask(__name__)

# Configure secret key for session management
app.config['SECRET_KEY'] = '9fb4d257480501774db0e3b11913a6aa'  # Use a secure and unique key in production

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///project.db'  # or another database URI
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app) #database is getting connected to the app

with app.app_context():
    db.create_all() # Creates the tables based on models


def intialize_admin():

    with app.app_context():
        # Check if the admin user already exists
        admin_user = User.query.filter_by(username='aditi').first()
        if not admin_user:          
            # Create a new admin user
            new_admin = User(
                username='aditi',
                full_name='Aditi Krishana',
                email = 'aditi@gmail.com',
                password = generate_password_hash('aditi123'),
                role='admin'
            )
            db.session.add(new_admin)
            db.session.commit()



@app.route('/')
def home():
    return render_template('home.html')

@app.route('/user_register', methods=['GET', 'POST'])
def user_register():
    if request.method == 'POST':
        username = request.form['username']
        full_name = request.form['full_name']
        email = request.form['email']
        password = request.form['password']
        role = request.form.get('role', 'user')

        new_user = User(username=username, 
                        full_name=full_name, 
                        email=email, 
                        password=generate_password_hash(password), 
                        role=role)
        
        db.session.add(new_user)
        db.session.commit()

        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('user_login'))
    return render_template('user_register.html')

@app.route('/user_login', methods=['GET', 'POST'])
def user_login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            flash('Login successful!', 'success')
            return redirect(url_for('user_dashboard'))
        else:
            flash('Invalid username or password', 'danger')
    return render_template('user_login.html')


@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        admin = User.query.filter_by(username=username, role='admin').first()

        if admin and check_password_hash(admin.password, password):
            session['admin_id'] = admin.id
            flash('Admin login successful!', 'success')
            return redirect(url_for('admin_dashboard'))  # or admin dashboard
        else:
            flash('Invalid admin credentials', 'danger')
    return render_template('admin_login.html')


@app.route('/admin_dashboard')
def admin_dashboard():
    if 'admin_id' not in session:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('admin_login'))

    users = User.query.all()
    posts = Post.query.all()
    return render_template('admin_dashboard.html', users=users, posts=posts)


@app.route('/user_dashboard')
def user_dashboard():
    if 'user_id' not in session:
        flash('Please log in to access dashboard', 'danger')
        return redirect(url_for('user_login'))

    user = User.query.get(session['user_id'])
    posts = Post.query.filter_by(author_id=user.id).all()
    return render_template('user_dashboard.html', user=user, posts=posts)


@app.route('/create_post', methods=['GET', 'POST'])
def create_post():
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        max_comments_per_user = int(request.form.get('max_comments_per_user', 3))
        author_id = session.get('user_id')

        new_post = Post(
            title=title,
            content=content,
            author_id=author_id,
            max_comments_per_user=max_comments_per_user
        )
        db.session.add(new_post)
        db.session.commit()
        flash("Post created successfully!", "success")
        return redirect(url_for('admin_dashboard'))

    return render_template('create_post.html')


@app.route('/edit_post/<int:post_id>', methods=['GET', 'POST'])
def edit_post(post_id):
    post = Post.query.get_or_404(post_id)

    # Check if current user is admin or author
    user_id = session.get('user_id')
    user = User.query.get(user_id)
    if not user or (user.role != 'admin' and post.author_id != user_id):
        flash("You don't have permission to edit this post.", "danger")
        return redirect(url_for('home'))

    if request.method == 'POST':
        post.title = request.form['title']
        post.content = request.form['content']
        max_comments_per_user = request.form.get('max_comments_per_user', 3)
        
        # Validate max_comments_per_user is a positive integer
        try:
            max_comments_per_user = int(max_comments_per_user)
            if max_comments_per_user < 1:
                raise ValueError
        except ValueError:
            flash("Max comments per user must be a positive integer.", "danger")
            return render_template('edit_post.html', post=post)

        post.max_comments_per_user = max_comments_per_user

        db.session.commit()
        flash("Post updated successfully.", "success")
        if user.role == 'admin':
            return redirect(url_for('admin_dashboard'))
        else:
            return redirect(url_for('user_dashboard'))

    return render_template('edit_post.html', post=post)

@app.route('/delete_post/<int:post_id>', methods=['POST'])
def delete_post(post_id):
    post = Post.query.get_or_404(post_id)

    user_id = session.get('user_id')
    user = User.query.get(user_id)

    if not user or (user.role != 'admin' and post.author_id != user_id):
        flash("You don't have permission to delete this post.", "danger")
        return redirect(url_for('home'))

    # Check if the post has any comments
    if post.comments and len(post.comments) > 0:
        flash("Cannot delete post. It has comments.", "warning")
        return redirect(url_for('admin_dashboard' if user.role == 'admin' else 'user_dashboard'))

    db.session.delete(post)
    db.session.commit()
    flash("Post deleted successfully.", "success")

    return redirect(url_for('admin_dashboard' if user.role == 'admin' else 'user_dashboard'))


@app.route('/add_comment/<int:post_id>', methods=['POST'])
def add_comment(post_id):
    user_id = session.get('user_id')
    if not user_id:
        flash("Please login to comment", "warning")
        return redirect(url_for('user_login'))

    post = Post.query.get_or_404(post_id)

    # Count user comments on this post
    user_comments_count = Comment.query.filter_by(post_id=post_id, user_id=user_id).count()

    if user_comments_count >= post.max_comments_per_user:
        flash(f"You have reached the maximum number of comments ({post.max_comments_per_user}) allowed on this post.", "danger")
        return redirect(url_for('view_post', post_id=post_id))

    content = request.form['content']
    new_comment = Comment(content=content, post_id=post_id, user_id=user_id)
    db.session.add(new_comment)
    db.session.commit()

    flash("Comment added successfully.", "success")
    return redirect(url_for('view_post', post_id=post_id))


@app.route('/summary')
def summary():
    if 'admin_id' not in session:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('admin_login'))

    total_users = User.query.count()
    total_posts = Post.query.count()
    total_comments = Comment.query.count()

    # Get top 5 users by number of comments
    
    active_users = db.session.query(
        User.full_name, func.count(Comment.id).label('comment_count')
    ).join(Comment).group_by(User.id).order_by(func.count(Comment.id).desc()).limit(5).all()

    return render_template('summary.html',
                           total_users=total_users,
                           total_posts=total_posts,
                           total_comments=total_comments,
                           active_users=active_users)


if __name__ == '__main__':
    intialize_admin()
    app.run(debug=True)
