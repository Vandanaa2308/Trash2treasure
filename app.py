# app.py
import os
from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

from extensions import db, login_manager
from config import Config
from flask_login import login_user, logout_user, login_required, current_user

# create app and load config
app = Flask(__name__)
app.config.from_object(Config)

# ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# initialize extensions (before importing models)
db.init_app(app)
login_manager.init_app(app)

# now import local modules
from models import User, Item, Message
from forms import RegisterForm, LoginForm, ContactForm, UploadForm, ChatForm

# user loader
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# index: show some items
@app.route('/')
def index():
    items = Item.query.order_by(Item.created_at.desc()).limit(6).all()
    return render_template('index.html', items=items)

# listings
@app.route('/listings')
def listings():
    q = request.args.get('q', '')
    cat = request.args.get('category', '')
    free = request.args.get('free', '')
    query = Item.query.filter_by(visible=True)
    if q:
        query = query.filter(Item.title.ilike(f'%{q}%'))
    if cat:
        query = query.filter_by(category=cat)
    if free == '1':
        query = query.filter_by(is_free=True)
    items = query.order_by(Item.created_at.desc()).all()
    return render_template('listings.html', items=items, q=q, cat=cat, free=free)

# item detail (show + contact owner)
@app.route('/item/<int:item_id>', methods=['GET', 'POST'])
def item_detail(item_id):
    item = Item.query.get_or_404(item_id)
    form = ContactForm()
    if form.validate_on_submit():
        # require login to send a message
        if not current_user.is_authenticated:
            flash('Please log in to contact the owner.', 'warning')
            return redirect(url_for('login'))

        # create a message record (owner will see it in inbox)
        content = f"Contact form message from {form.name.data} ({form.email.data}):\n\n{form.message.data}"
        msg = Message(
            item_id=item.id,
            sender_id=current_user.id,
            recipient_id=item.user_id,
            content=content
        )
        db.session.add(msg)
        db.session.commit()
        flash('Message sent to owner', 'success')
        return redirect(url_for('item_detail', item_id=item_id))

    return render_template('item.html', item=item, form=form)

# upload (must login)
@app.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    form = UploadForm()
    if request.method == 'POST' and form.validate_on_submit():
        file = request.files.get('image')
        filename = None
        if file and file.filename:
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        # determine price/free flag
        price_value = form.price.data
        if price_value is None:
            price_value = 0.0

        is_free_flag = (float(price_value) == 0.0)

        item = Item(
            title=form.title.data,
            description=form.description.data,
            category=form.category.data,
            price=price_value,
            quantity=form.quantity.data,
            location=form.location.data,
            image_filename=filename,
            user_id=current_user.id,
            is_free=is_free_flag
        )
        db.session.add(item)
        db.session.commit()
        flash('Item uploaded', 'success')
        return redirect(url_for('listings'))
    return render_template('upload.html', form=form)

# serve uploaded files
@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# register
@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = RegisterForm()
    if form.validate_on_submit():
        if User.query.filter_by(email=form.email.data).first():
            flash('Email already registered', 'warning')
            return redirect(url_for('register'))
        user = User(
            name=form.name.data,
            email=form.email.data,
            phone=form.phone.data or '',
            password_hash=generate_password_hash(form.password.data)
        )
        db.session.add(user)
        db.session.commit()
        login_user(user)
        flash('Registered and logged in', 'success')
        return redirect(url_for('index'))
    return render_template('register.html', form=form)

# login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and check_password_hash(user.password_hash, form.password.data):
            login_user(user, remember=form.remember.data)
            flash('Logged in', 'success')
            return redirect(url_for('index'))
        flash('Invalid credentials', 'danger')
    return render_template('login.html', form=form)

# logout
@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out', 'info')
    return redirect(url_for('index'))

# profile
@app.route('/profile')
@login_required
def profile():
    return render_template('profile.html')

# chat route (send + display messages about a specific item) - kept for compatibility
@app.route('/chat/<int:item_id>', methods=['GET', 'POST'])
@login_required
def chat_with_owner(item_id):
    item = Item.query.get_or_404(item_id)
    owner = item.user
    if owner is None:
        flash('Owner not found', 'danger')
        return redirect(url_for('listings'))

    form = ChatForm()
    if form.validate_on_submit():
        text = form.message.data.strip()
        if text:
            msg = Message(
                item_id=item.id,
                sender_id=current_user.id,
                recipient_id=owner.id,
                content=text
            )
            db.session.add(msg)
            db.session.commit()
            return redirect(url_for('chat_with_owner', item_id=item_id))

    # load messages between current_user and owner for this item
    conv = Message.query.filter(
        Message.item_id == item.id
    ).filter(
        ((Message.sender_id == current_user.id) & (Message.recipient_id == owner.id))
        | ((Message.sender_id == owner.id) & (Message.recipient_id == current_user.id))
    ).order_by(Message.timestamp).all()

    return render_template('chat.html', item=item, owner=owner, messages=conv, form=form)

# inbox & conversation features
from sqlalchemy import or_

@app.route('/inbox')
@login_required
def inbox():
    # gather messages that involve current user, newest first
    msgs = Message.query.filter(
        or_(Message.sender_id == current_user.id, Message.recipient_id == current_user.id)
    ).order_by(Message.timestamp.desc()).all()

    # collapse into unique threads keyed by (item_id, other_user_id)
    threads = {}
    for m in msgs:
        other = m.recipient_id if m.sender_id == current_user.id else m.sender_id
        key = (m.item_id, other)
        if key not in threads:
            threads[key] = m

    thread_list = []
    for (item_id, other_id), last_msg in threads.items():
        other_user = User.query.get(other_id)
        item = Item.query.get(item_id)
        thread_list.append({
            "item": item,
            "other": other_user,
            "last_message": last_msg
        })

    return render_template('inbox.html', threads=thread_list)

@app.route('/conversation/<int:item_id>/<int:other_id>', methods=['GET', 'POST'])
@login_required
def conversation(item_id, other_id):
    other = User.query.get_or_404(other_id)
    item = Item.query.get_or_404(item_id)

    # ensure current_user participates in conversation (either owner or the other)
    if current_user.id not in (item.user_id, other.id):
        flash('Not authorized to view this conversation.', 'danger')
        return redirect(url_for('inbox'))

    form = ChatForm()
    if form.validate_on_submit():
        text = form.message.data.strip()
        if text:
            msg = Message(
                item_id=item.id,
                sender_id=current_user.id,
                recipient_id=other.id,
                content=text
            )
            db.session.add(msg)
            db.session.commit()
            return redirect(url_for('conversation', item_id=item_id, other_id=other_id))

    conv = Message.query.filter(
        Message.item_id == item.id
    ).filter(
        ((Message.sender_id == current_user.id) & (Message.recipient_id == other.id))
        | ((Message.sender_id == other.id) & (Message.recipient_id == current_user.id))
    ).order_by(Message.timestamp).all()

    return render_template('conversation.html', item=item, other=other, messages=conv, form=form)

# admin & dashboard placeholders
@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

@app.route('/admin')
def admin():
    return render_template('admin.html')

# run
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
