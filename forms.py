# forms.py
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, TextAreaField, SubmitField, BooleanField, FloatField, IntegerField
from wtforms.validators import DataRequired, Email, Length, Optional, NumberRange

class RegisterForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired(), Length(max=120)])
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=150)])
    phone = StringField('Phone', validators=[Optional(), Length(max=30)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=5)])
    submit = SubmitField('Register')

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=150)])
    password = PasswordField('Password', validators=[DataRequired()])
    remember = BooleanField('Remember me')
    submit = SubmitField('Login')

class ContactForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    message = TextAreaField('Message', validators=[DataRequired(), Length(max=2000)])
    submit = SubmitField('Send')

class UploadForm(FlaskForm):
    title = StringField('Title', validators=[DataRequired(), Length(max=200)])
    description = TextAreaField('Description', validators=[Optional(), Length(max=2000)])
    category = StringField('Category', validators=[Optional(), Length(max=80)])
    price = FloatField('Price', validators=[Optional()])
    quantity = StringField('Quantity', validators=[Optional()])
    location = StringField('Location', validators=[Optional()])
    submit = SubmitField('Upload')

class ChatForm(FlaskForm):
    message = StringField('Message', validators=[DataRequired(), Length(max=1000)])
    submit = SubmitField('Send')

class RatingForm(FlaskForm):
    stars = IntegerField('Stars', validators=[DataRequired(), NumberRange(min=1, max=5)])
    review = TextAreaField('Review', validators=[Optional(), Length(max=1000)])
    submit = SubmitField('Rate')
