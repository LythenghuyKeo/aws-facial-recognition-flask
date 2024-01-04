from flask import Flask, render_template, request, jsonify, Response
import boto3
from config import S3_BUCKET,S3_KEY,S3_SECRET_ACCESS_KEY
from flask_bootstrap import Bootstrap
from dotenv import load_dotenv
import os
load_dotenv()  
s3_bucket = os.environ.get('S3_BUCKET')
s3_key = os.environ.get('S3_KEY')
s3_secret_access_key = os.environ.get('S3_SECRET_ACCESS_KEY')
# import camera
# Import other necessary modules
s3 = boto3.client(
    's3',
    aws_access_key_id=s3_key,
    aws_secret_access_key=s3_secret_access_key
)

app = Flask(__name__)
Bootstrap(app)
@app.route('/')
def index():
    return render_template('index.html')
@app.route('/admin')
def admin():
    s3_resource = boto3.resource('s3')
    my_bucket = s3_resource.Bucket(s3_bucket)
    summaries = my_bucket.objects.all()
    return render_template('admin.html',my_bucket=my_bucket,files=summaries)
@app.route('/upload_data',methods=['POST'])
def upload_data():
    user_name = request.form.get('name')
    id = request.form.get('id')
    department = request.form.get('department')
    role = request.form.get('role')
    file = request.files['file']
    s3_resource = boto3.resource('s3')
    my_bucket = s3_resource.Bucket(s3_bucket)
    my_bucket.Object(file.filename).put(Body=file)
    return "uploaded"
@app.route('/scan')
def scan():
      return render_template('scan.html')
@app.route('/detection', methods=['POST'])
def detection():
    file = request.files.get('file')
    if not file:
        return jsonify({'success': False, 'message': 'No file provided'}), 400
    else:
        return jsonify({'success': True, 'message': 'file provided'}), 400
    # # Save file temporarily
    # file_path = os.path.join('temp', 'webcam.jpg')
    # file.save(file_path)

    # # Upload the file to S3
    # file_name = "webcam.jpg"  # Ensure unique file names in production
    # s3_client.upload_file(file_path, "your-s3-bucket-name", file_name)

    # # Authenticate using Rekognition
    # response = rekognition_client.search_faces_by_image(
    #     CollectionId='your-collection-id',
    #     Image={'S3Object': {'Bucket': "your-s3-bucket-name", 'Name': file_name}},
    #     MaxFaces=1,
    #     FaceMatchThreshold=90
    # )

    # os.remove(file_path)  # Remove the temporary file

    # if response['FaceMatches']:
    #     # Assuming face match found, update database
    #     user_id = response['FaceMatches'][0]['Face']['ExternalImageId']
    #     attendance_record = Attendance.query.filter_by(user_id=user_id).first()
    #     if attendance_record:
    #         attendance_record.last_attendance = db.func.now()
    #         db.session.commit()

    #     # Send back the user ID
    #     return jsonify({'success': True, 'user_id': user_id})
    # else:
    #     return jsonify({'success': False, 'message': 'Face not recognized'}), 401

# @app.route('/video_feed')
# def video_feed():
#     return Response(camera.gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

# @app.route('/capture', methods=['POST'])
# def capture_image():
#     # Process the received image for facial recognition
#     # ...
#     return jsonify({"message": "Image processed"})

if __name__ == '__main__':
    app.run(debug=True)
