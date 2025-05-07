from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import mysql.connector
from werkzeug.utils import secure_filename
import subprocess

app = Flask(__name__)
CORS(app)  # Cho phép frontend gọi API
UPLOAD_FOLDER = './uploads'
ALLOWED_EXTENSIONS = {'skp'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Kết nối MariaDB
db = mysql.connector.connect(
    host="localhost",
    user="baotva",
    password="Ab12051982",
    database="sketchup_app"
)
cursor = db.cursor()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/upload', methods=['POST'])
def upload_model():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        
        # Lưu vào database
        cursor.execute("INSERT INTO Models (model_name, file_path) VALUES (%s, %s)", 
                      (filename, file_path))
        db.commit()
        model_id = cursor.lastrowid
        
        # Gọi script FreeCAD để bóc tách
        try:
            result = subprocess.run(['python3', 'freecad_script.py', file_path], 
                                  capture_output=True, text=True)
            furniture_list = eval(result.stdout)  # Giả sử script trả về danh sách đồ dùng
        except Exception as e:
            return jsonify({'error': str(e)}), 500
        
        # Lưu đồ dùng vào database
        for furniture in furniture_list:
            cursor.execute("INSERT INTO Furniture (name, description, price) VALUES (%s, %s, %s)",
                          (furniture['name'], furniture['description'], furniture['price']))
            furniture_id = cursor.lastrowid
            cursor.execute("INSERT INTO ModelFurniture (model_id, furniture_id, quantity) VALUES (%s, %s, %s)",
                          (model_id, furniture_id, furniture.get('quantity', 1)))
        db.commit()
        
        return jsonify({'model_id': model_id, 'furniture': furniture_list}), 200
    return jsonify({'error': 'Invalid file type'}), 400

@app.route('/model/<int:model_id>/furniture', methods=['GET'])
def get_furniture(model_id):
    cursor.execute("""
        SELECT f.furniture_id, f.name, f.description, f.price, mf.quantity
        FROM Furniture f
        JOIN ModelFurniture mf ON f.furniture_id = mf.furniture_id
        WHERE mf.model_id = %s
    """, (model_id,))
    furniture = [
        {'id': row[0], 'name': row[1], 'description': row[2], 'price': row[3], 'quantity': row[4]}
        for row in cursor.fetchall()
    ]
    return jsonify(furniture), 200

@app.route('/model/<int:model_id>/furniture/<int:furniture_id>', methods=['PUT'])
def update_furniture(model_id, furniture_id):
    data = request.json
    quantity = data.get('quantity', 1)
    cursor.execute("UPDATE ModelFurniture SET quantity = %s WHERE model_id = %s AND furniture_id = %s",
                  (quantity, model_id, furniture_id))
    db.commit()
    return jsonify({'message': 'Updated successfully'}), 200

if __name__ == '__main__':
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    app.run(debug=True)