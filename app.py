# app.py
import os
from datetime import datetime
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
from models import User, Item, Message, Rating
from forms import RegisterForm, LoginForm, ContactForm, UploadForm, ChatForm, RatingForm

# user loader
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# index: show some items
@app.route('/')
def index():
    items = Item.query.filter_by(visible=True, is_sold=False).order_by(Item.created_at.desc()).limit(6).all()
    return render_template('index.html', items=items)

# listings
@app.route('/listings')
def listings():
    q = request.args.get('q', '')
    cat = request.args.get('category', '')
    free = request.args.get('free', '')
    query = Item.query.filter_by(visible=True, is_sold=False)
    if q:
        query = query.filter(Item.title.ilike(f'%{q}%'))
    if cat:
        query = query.filter_by(category=cat)
    if free == '1':
        query = query.filter_by(is_free=True)
    items = query.order_by(Item.created_at.desc()).all()
    return render_template('listings.html', items=items, q=q, cat=cat, free=free)

# item detail + rating & contact handling
@app.route('/item/<int:item_id>', methods=['GET', 'POST'])
def item_detail(item_id):
    item = Item.query.get_or_404(item_id)

    # forms (use prefixes if needed, but the template uses simple names)
    contact_form = ContactForm()
    rating_form = RatingForm()

    # --- CONTACT: store as Message in DB (owner will see it in their inbox)
    if contact_form.validate_on_submit() and 'send_contact' in request.form:
        # require user to be logged in to store sender_id
        if not current_user.is_authenticated:
            flash('Please log in to contact the owner.', 'warning')
            return redirect(url_for('login'))

        # build a friendly message content
        contact_text = f"Contact request from {contact_form.name.data} ({contact_form.email.data}):\n\n{contact_form.message.data}"
        msg = Message(
            item_id=item.id,
            sender_id=current_user.id,
            recipient_id=item.user_id,
            content=contact_text,
            timestamp=datetime.utcnow()
        )
        db.session.add(msg)
        db.session.commit()
        flash('Message sent to owner.', 'success')
        return redirect(url_for('item_detail', item_id=item_id))

    # --- RATING: integer 1..5, one rating per user per item (update if exists)
    if rating_form.validate_on_submit() and 'submit_rating' in request.form:
        # must be logged in
        if not current_user.is_authenticated:
            flash('Please login to submit rating', 'warning')
            return redirect(url_for('login'))

        # owner cannot rate own item
        if current_user.id == item.user_id:
            flash('You cannot rate your own item', 'warning')
            return redirect(url_for('item_detail', item_id=item_id))

        stars = int(rating_form.stars.data)
        review = rating_form.review.data or ''

        existing = Rating.query.filter_by(item_id=item.id, user_id=current_user.id).first()
        if existing:
            existing.stars = stars
            existing.review = review
            # update timestamp if field exists
            try:
                existing.timestamp = datetime.utcnow()
            except Exception:
                pass
            flash('Your rating was updated', 'success')
        else:
            r = Rating(item_id=item.id, user_id=current_user.id, stars=stars, review=review, timestamp=datetime.utcnow())
            db.session.add(r)
            flash('Thank you for your rating', 'success')
        db.session.commit()
        return redirect(url_for('item_detail', item_id=item_id))

    # compute average and count for this item
    avg = db.session.query(db.func.avg(Rating.stars)).filter(Rating.item_id == item.id).scalar()
    count = Rating.query.filter_by(item_id=item.id).count()
    avg = float(avg) if avg is not None else None

    # load all reviews (newest first) joined with the user who rated
    all_reviews = db.session.query(Rating, User).join(User, Rating.user_id == User.id) \
                    .filter(Rating.item_id == item.id) \
                    .order_by(Rating.timestamp.desc()).all()

    return render_template(
        'item.html',
        item=item,
        form=contact_form,
        rating_form=rating_form,
        avg_rating=avg,
        rating_count=count,
        all_reviews=all_reviews
    )

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
        item = Item(
            title=form.title.data,
            description=form.description.data,
            category=form.category.data,
            price=form.price.data or 0.0,
            quantity=form.quantity.data,
            location=form.location.data,
            image_filename=filename,
            user_id=current_user.id
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
    # show user's items and ratings
    items = Item.query.filter_by(user_id=current_user.id).order_by(Item.created_at.desc()).all()
    return render_template('profile.html', items=items)

# chat route (send + display messages about a specific item)
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
                content=text,
                timestamp=datetime.utcnow()
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

# DELETE item (owner only)
@app.route('/delete_item/<int:item_id>', methods=['POST'])
@login_required
def delete_item(item_id):
    item = Item.query.get_or_404(item_id)
    if item.user_id != current_user.id:
        flash("You are not allowed to delete this item.", "danger")
        return redirect(url_for('item_detail', item_id=item_id))

    # delete image file if exists
    if item.image_filename:
        image_path = os.path.join(app.config['UPLOAD_FOLDER'], item.image_filename)
        if os.path.exists(image_path):
            try:
                os.remove(image_path)
            except Exception:
                pass

    db.session.delete(item)
    db.session.commit()
    flash("Item deleted successfully!", "success")
    return redirect(url_for('listings'))

# Mark as sold / unmark
@app.route('/mark_sold/<int:item_id>', methods=['POST'])
@login_required
def mark_sold(item_id):
    item = Item.query.get_or_404(item_id)
    if item.user_id != current_user.id:
        flash("You cannot change this item.", "danger")
        return redirect(url_for('item_detail', item_id=item_id))
    item.is_sold = True
    db.session.commit()
    flash("Item marked as sold.", "success")
    return redirect(url_for('item_detail', item_id=item_id))

@app.route('/unmark_sold/<int:item_id>', methods=['POST'])
@login_required
def unmark_sold(item_id):
    item = Item.query.get_or_404(item_id)
    if item.user_id != current_user.id:
        flash("You cannot change this item.", "danger")
        return redirect(url_for('item_detail', item_id=item_id))
    item.is_sold = False
    db.session.commit()
    flash("Item marked available.", "success")
    return redirect(url_for('item_detail', item_id=item_id))

# Inbox - show conversations for owner (grouped by item + sender)
@app.route('/inbox')
@login_required
def inbox():
    # find items owned by current user
    my_items = Item.query.filter_by(user_id=current_user.id).all()
    item_ids = [i.id for i in my_items]
    conversations = []

    if item_ids:
        # get distinct pairs (item_id, sender_id) where sender != owner
        rows = db.session.query(Message.item_id, Message.sender_id, db.func.max(Message.timestamp).label('last_time')) \
                 .filter(Message.item_id.in_(item_ids)) \
                 .group_by(Message.item_id, Message.sender_id) \
                 .order_by(db.desc('last_time')).all()

        for item_id, sender_id, last_time in rows:
            if sender_id == current_user.id:
                continue
            item = Item.query.get(item_id)
            sender = User.query.get(sender_id)
            last_msg = Message.query.filter_by(item_id=item_id, sender_id=sender_id) \
                         .order_by(Message.timestamp.desc()).first()
            conversations.append({
                'item': item,
                'sender': sender,
                'last_message': last_msg,
                'last_time': last_time
            })

    return render_template('inbox.html', conversations=conversations)

# Conversation view between owner and one other user for an item
@app.route('/conversation/<int:item_id>/<int:other_id>', methods=['GET', 'POST'])
@login_required
def conversation(item_id, other_id):
    item = Item.query.get_or_404(item_id)
    # only owner or the other user can view
    if current_user.id not in (item.user_id, other_id):
        flash("Not authorized", "danger")
        return redirect(url_for('index'))

    # sending message from current_user to other participant
    if request.method == 'POST':
        text = request.form.get('message', '').strip()
        if text:
            recipient_id = other_id if current_user.id == item.user_id else item.user_id
            msg = Message(item_id=item.id, sender_id=current_user.id, recipient_id=recipient_id, content=text, timestamp=datetime.utcnow())
            db.session.add(msg)
            db.session.commit()
            return redirect(url_for('conversation', item_id=item_id, other_id=other_id))

    # load all messages between these two users for this item
    messages = Message.query.filter(
        Message.item_id == item_id
    ).filter(
        ((Message.sender_id == current_user.id) & (Message.recipient_id == other_id)) |
        ((Message.sender_id == other_id) & (Message.recipient_id == current_user.id))
    ).order_by(Message.timestamp.asc()).all()

    other_user = User.query.get_or_404(other_id)
    return render_template('conversation.html', item=item, other_user=other_user, messages=messages)

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
