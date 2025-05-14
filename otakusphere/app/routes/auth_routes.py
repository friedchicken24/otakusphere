from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, current_user, login_required
from app import db
from app.models import User
from app.forms import LoginForm, RegistrationForm

bp = Blueprint('auth', __name__)

@bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('user.home'))
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(username=form.username.data, email=form.email.data)
        user.set_password(form.password.data)
        # Mặc định user đầu tiên đăng ký là admin (cho mục đích dev)
        if User.query.count() == 0:
            user.role = 'admin'
        db.session.add(user)
        db.session.commit()
        flash('Chúc mừng, bạn đã đăng ký thành công!', 'success')
        return redirect(url_for('auth.login'))
    return render_template('auth/register.html', title='Đăng ký', form=form)

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('user.home'))
    form = LoginForm()
    if form.validate_on_submit():
        user_by_username = User.query.filter_by(username=form.username_or_email.data).first()
        user_by_email = User.query.filter_by(email=form.username_or_email.data).first()
        user = user_by_username or user_by_email

        if user is None or not user.check_password(form.password.data):
            flash('Tên đăng nhập hoặc mật khẩu không đúng.', 'danger')
            return redirect(url_for('auth.login'))
        if not user.is_active:
            flash('Tài khoản của bạn đã bị vô hiệu hóa.', 'warning')
            return redirect(url_for('auth.login'))
        
        login_user(user, remember=form.remember_me.data)
        next_page = request.args.get('next')
        if not next_page or not next_page.startswith('/'):
            if user.role == 'admin':
                next_page = url_for('admin.dashboard')
            else:
                next_page = url_for('user.home')
        flash('Đăng nhập thành công!', 'success')
        return redirect(next_page)
    return render_template('auth/login.html', title='Đăng nhập', form=form)

@bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Bạn đã đăng xuất.', 'info')
    return redirect(url_for('user.home'))