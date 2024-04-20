from flask import Flask, make_response, request, jsonify, url_for
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from datetime import datetime, timedelta
import datetime
import os
from flask import Flask, send_from_directory
from flask_cors import CORS
from flask_jwt_extended import JWTManager, get_jwt_identity, jwt_required, create_access_token
from flask_bcrypt import Bcrypt
from werkzeug.utils import secure_filename


app = Flask(__name__)
CORS(app)  # Enable CORS for all routes
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///library.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'your_secret_key'  # Add a secret key for Flask session management

# JWT configuration
app.config['JWT_SECRET_KEY'] = 'your_jwt_secret_key'
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(hours=12)  # Set the expiration time for token
app.config["JWT_ALGORITHM"] = "HS256"  # Set the algorithm
jwt = JWTManager(app)    # Initialize JWT 
bcrypt = Bcrypt(app)


db = SQLAlchemy(app)

# Define the directory where uploaded photos will be stored
UPLOAD_FOLDER = 'static'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}  # Define allowed file extensions
app.config["UPLOAD_FOLDER"] = "static"

# Function to check if the file extension is allowed
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory('static', filename)

class Book(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    author = db.Column(db.String(100), nullable=False)
    year_published = db.Column(db.Integer, nullable=False)
    book_type = db.Column(db.Integer, nullable=False)
    photo = db.Column(db.String(255))  # Add a field for storing the photo
    loans = relationship('Loan', backref='book', lazy=True)
    
class Customer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    city = db.Column(db.String(100), nullable=False)
    age = db.Column(db.Integer, nullable=False)
    loans = relationship('Loan', backref='customer', lazy=True)

class Loan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cust_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=False)
    book_id = db.Column(db.Integer, db.ForeignKey('book.id'), nullable=False)
    loan_date = db.Column(db.Date, nullable=False)
    return_date = db.Column(db.Date)
    status = db.Column(db.String(20), default='not late')  # Default value indicating the loan is not late

    


@app.route('/add_book', methods=['POST'])
def add_book():
    name = request.form['name']
    author = request.form['author']
    year_published = request.form['year_published']
    book_type = request.form['book_type']
    
    # Check if the post request has the file part
    if 'photo' not in request.files:
        # Set a default photo filename
        photo_filename = 'defult.png'
    else:
        file = request.files['photo']
        
        # If the user does not select a file, the browser submits an empty file without a filename
        if file.filename == '':
            # Set a default photo filename
            photo_filename = 'defult.png'
        else:
            # Check if the file extension is allowed
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                photo_filename = filename  # Store the filename in the database
            else:
                return jsonify({"error": "File type not allowed"}), 400

    # Create a new Book object and add it to the database
    new_book = Book(name=name, author=author, year_published=year_published, book_type=book_type, photo=photo_filename)
    db.session.add(new_book)
    db.session.commit()
    
    return jsonify({"message": "New book added successfully"})



@app.route('/books')
def show_all_books():
    books = Book.query.all()
    book_list = []
    for book in books:
        if book.photo:
            photo_url = url_for('static', filename=book.photo)
        else:
            # If the book doesn't have a photo, use the default photo
            photo_url = url_for('static', filename='defult.png')
        
        book_data = {
            "id": book.id,
            "name": book.name,
            "author": book.author,
            "year_published": book.year_published,
            "book_type": book.book_type,
            "photo": photo_url
        }
        book_list.append(book_data)
    
    return jsonify(book_list)

# Route to delete a book
@app.route('/books/<int:book_id>', methods=['DELETE'])
def delete_book(book_id):
    try:
        book = Book.query.get(book_id)
        if book:
            db.session.delete(book)
            db.session.commit()
            return jsonify({"message": "Book RETURNED successfully"}), 200
        else:
            return jsonify({"error": "Book not found"}), 404
    except Exception as e:
        # Log the exception or print it for debugging
        print("Error deleting book:", e)
        return jsonify({"error": "An error occurred while deleting the book"}), 500


@app.route('/loan_book', methods=['POST'])
def loan_book():
    request_data = request.get_json()
    customer_name = request_data['customer_name']
    book_name = request_data['book_name']
    current_datetime = datetime.datetime.now().date()  # Get current date

    # Retrieve customer and book IDs based on names
    customer = Customer.query.filter_by(name=customer_name).first()
    book = Book.query.filter_by(name=book_name).first()

    if customer and book:
        # Calculate return date based on book type
        if book.book_type == 1:  # Regular book
            return_date = current_datetime + datetime.timedelta(days=10)  # Return in up to 10 days
        elif book.book_type == 2:  # Reference book
            return_date = current_datetime + datetime.timedelta(days=5)  # Return in up to 5 days
        elif book.book_type == 3:  # Special book
            return_date = current_datetime + datetime.timedelta(days=2)  # Return in up to 2 days
        else:
            return jsonify({"error": "Invalid book type"}), 400

        # Perform the loan operation using the retrieved IDs and calculated return date
        new_loan = Loan(cust_id=customer.id, book_id=book.id, loan_date=current_datetime, return_date=return_date)
        db.session.add(new_loan)
        db.session.commit()
        return jsonify({"message": "Book loaned successfully"})
    else:
        return jsonify({"message": "Customer or book not found"}), 404

    
    # Route to fetch all loans
@app.route('/loans')
def show_all_loans():
    loans = Loan.query.all()
    loan_list = [{
        "id": loan.id,
        "customer_id": loan.customer.id,
        "customer_name": loan.customer.name,
        "book_id": loan.book.id,
        "book_name": loan.book.name,
        "loan_date": loan.loan_date,
        "return_date": loan.return_date,
        "status": loan.status  # Include loan status in the response
    } for loan in loans]
    return jsonify(loan_list)


# Route to fetch late loans
@app.route('/late_loans')
def show_late_loans():
    # Query the database for loans with status "late"
    late_loans = Loan.query.filter_by(status='late').all()

    # Prepare the response data
    late_loan_list = [{
        "id": loan.id,
        "customer_id": loan.customer.id,  # Accessing customer ID through relationship
        "customer_name": loan.customer.name,  # Accessing customer name through relationship
        "book_id": loan.book.id,
        "book_name": loan.book.name,
        "loan_date": loan.loan_date,
        "return_date": loan.return_date
    } for loan in late_loans]
    
    return jsonify(late_loan_list)




# Route to delete a loan
@app.route('/loans/<int:loan_id>', methods=['DELETE'])
def delete_loan(loan_id):
    try:
        loan = Loan.query.get(loan_id)
        if loan:
            db.session.delete(loan)
            db.session.commit()
            return jsonify({"message": "book returned successfully"}), 200
        else:
            return jsonify({"error": "Loan not found"}), 404
    except Exception as e:
        # Log the exception or print it for debugging
        print("Error deleting loan:", e)
        return jsonify({"error": "An error occurred while deleting the loan"}), 500

@app.route('/mark_as_late/<int:loan_id>', methods=['PUT'])
def mark_as_late(loan_id):
    loan = Loan.query.get_or_404(loan_id)
    loan.status = 'late'  # Update the status to 'late'
    db.session.commit()

    # Retrieve the late loans from local storage
    late_loans = request.json.get('late_loans', [])
    late_loans.append({
        "id": loan.id,
        "customer_id": loan.customer.id,
        "customer_name": loan.customer.name,
        "book_id": loan.book.id,
        "book_name": loan.book.name,
        "loan_date": loan.loan_date,
        "return_date": loan.return_date
    })

    # Update local storage with the modified late loans
    request.json['late_loans'] = late_loans

    return jsonify({'message': 'Loan marked as late successfully'})



# Routes for Customer operations
@app.route('/customers')
def show_all_customers():
    customers = Customer.query.all()
    customer_list = [{"id": customer.id, "name": customer.name, "city": customer.city, "age": customer.age} for customer in customers]
    return jsonify(customer_list)

# Route for adding a new customer
@app.route('/add_customer', methods=['POST'])
def add_customer():
    data = request.json
    name = data.get('name')
    city = data.get('city')
    age = data.get('age')

    new_customer = Customer(name=name, city=city, age=age)
    db.session.add(new_customer)
    db.session.commit()

    return jsonify({'message': 'Customer added successfully'}), 201

# Route to delete a customer
@app.route('/customers/<int:customer_id>', methods=['DELETE'])
def delete_customer(customer_id):
    try:
        customer = Customer.query.get(customer_id)
        if customer:
            db.session.delete(customer)
            db.session.commit()
            return jsonify({"message": "Customer deleted successfully"}), 200
        else:
            return jsonify({"error": "Customer not found"}), 404
    except Exception as e:
        # Log the exception or print it for debugging
        print("Error deleting customer:", e)
        return jsonify({"error": "An error occurred while deleting the customer"}), 500


# Route for searching books by name
@app.route('/search_books', methods=['GET'])
def search_books():
    search_query = request.args.get('query')  # Get the search query from the request
    if not search_query:
        return jsonify({"error": "Please provide a search query"}), 400

    # Perform a case-insensitive search for books containing the search query in their name
    books = Book.query.filter(Book.name.ilike(f"%{search_query}%")).all()
    
    # Prepare the response data
    book_list = [{"id": book.id, "name": book.name, "author": book.author, "year_published": book.year_published, "book_type": book.book_type} for book in books]
    return jsonify(book_list)

# Route for searching customers by name
@app.route('/search_customers', methods=['GET'])
def search_customers():
    search_query = request.args.get('query')  # Get the search query from the request
    if not search_query:
        return jsonify({"error": "Please provide a search query"}), 400

    # Perform a case-insensitive search for customers containing the search query in their name
    customers = Customer.query.filter(Customer.name.ilike(f"%{search_query}%")).all()
    
    # Prepare the response data
    customer_list = [{"id": customer.id, "name": customer.name, "city": customer.city, "age": customer.age} for customer in customers]
    return jsonify(customer_list)

# Defining Users Table
class User(db.Model):
    user_id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(300), nullable=False)
    user_role = db.Column(db.String(50), default='user') 
    
    
    
    
    # route for registering new user
    
@app.route('/user/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    role = data.get('role', 'user')  # Default to 'user' if role is not provided

    if not username or not password or not role:
        return jsonify({"error": "Missing required fields"}), 400

    hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')

    new_user = User(username=username, password=hashed_password, user_role=role)
    db.session.add(new_user)
    db.session.commit()

    return jsonify({"message": "User registered successfully"}), 201

@app.route('/user/login', methods=['POST'])              
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({"error": "Missing required fields"}), 400

    user = User.query.filter_by(username=username).first()

    if not user or not bcrypt.check_password_hash(user.password, password):
        return jsonify({"error": "Invalid credentials"}), 401

    # Create JWT token
    expires = datetime.timedelta(days=7)  # Token expiration time
    access_token = create_access_token(identity=user.user_id, expires_delta=expires)

    # Store the token in localStorage
    response = make_response(jsonify({"access_token": access_token}), 200)
    response.set_cookie('access_token', access_token)  # Set the token in a cookie
    return response
#logout

@app.route("/logout")           
@jwt_required
def logout():
    # Clear the access token cookie
    response = make_response(jsonify({"message": "You have been logged out."}), 200)
    response.set_cookie('access_token', '', expires=0)  # Clear the access token cookie
    return response


@app.route('/api/dashboard')
def admin_dashboard():
    total_books = len(Book.query.all())
    total_customers = len(Customer.query.all())
    total_loans = len(Loan.query.all())
    late_loans = len(Loan.query.filter(Loan.return_date < datetime.datetime.now().date()).all())
    
    return jsonify({
        'total_books': total_books,
        'total_customers': total_customers,
        'total_loans': total_loans,
        'late_loans': late_loans
    })
    
    
    
    

# Define the root route to serve the frontend
# Define routes to serve HTML files from the frontend folder
@app.route('/')
def home():
    # Serve the index.html file from the frontend folder
    return send_from_directory('../frontend', 'home.html')

@app.route('/books.html')
def books():
    # Serve the books.html file from the frontend folder
    return send_from_directory('../frontend', 'books.html')

@app.route('/customers.html')
def customers():
    # Serve the books.html file from the frontend folder
    return send_from_directory('../frontend', 'customers.html')

@app.route('/loans.html')
def loans():
    # Serve the books.html file from the frontend folder
    return send_from_directory('../frontend', 'loans.html')

@app.route('/login.html')
def login_page():  # Renamed the function to avoid conflict
    # Serve the books.html file from the frontend folder
    return send_from_directory('../frontend', 'login.html')

@app.route('/search.html')
def search():
    # Serve the books.html file from the frontend folder
    return send_from_directory('../frontend', 'search.html')

@app.route('/dashboard.html')
def dashboard():
    # Serve the books.html file from the frontend folder
    return send_from_directory('../frontend', 'dashboard.html')



if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
