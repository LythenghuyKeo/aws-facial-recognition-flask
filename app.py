from flask import Flask, render_template, request, jsonify, Response
import boto3
from flask_bootstrap import Bootstrap
from dotenv import load_dotenv
from flask_sqlalchemy import SQLAlchemy,session
import os
from datetime import datetime


load_dotenv()  


s3_bucket = os.environ.get('S3_BUCKET')
s3_key = os.environ.get('S3_KEY')
s3_secret_access_key = os.environ.get('S3_SECRET_ACCESS_KEY')
s3 = boto3.client(
    's3',
    aws_access_key_id=s3_key,
    aws_secret_access_key=s3_secret_access_key
)
rekognition_client=boto3.client(
    'rekognition',
    aws_access_key_id=s3_key,
    aws_secret_access_key=s3_secret_access_key
)
collection_id = "KIT_0089089000"  #


app = Flask(__name__)
Bootstrap(app)


#Database configuration
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///project.db"
db = SQLAlchemy(app)
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    grade = db.Column(db.Integer,nullable=False)
    imageRef = db.Column(db.String(200),nullable=False)
     # Relationship to Attendance
    attendances = db.relationship('Attendance', backref='user', lazy=True)
class Attendance(db.Model):
    id= db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    arrived_at =db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String, nullable=False)

def generate_id():
    max_id = db.session.query(db.func.max(User.id)).scalar()
    return 202401000 if max_id is None else max_id + 1
#app routing
@app.before_request
def create_tables():
    db.create_all()



@app.route('/')
def index():
    return render_template('index.html')



@app.route('/get_all_file')
def get_all_file():
    s3_resource = boto3.resource('s3')
    my_bucket = s3_resource.Bucket(s3_bucket)
    summaries = my_bucket.objects.all()
    return render_template('files.html',my_bucket=my_bucket,files=summaries)



@app.route('/user')
def user():
    return render_template('user.html')

@app.route('/user/<int:grade>')
def my_student(grade):
    my_students = User.query.filter_by(grade=grade).all()
    return render_template('student.html',students=my_students)

@app.route('/admin')
def admin():
    return render_template('admin.html')



@app.route('/upload_data',methods=['POST'])
def upload_data():
    #Request Data
    user_name = request.form.get('name')
    email = request.form.get('email')
    id=generate_id()
    grade = int(request.form.get('grade'))
    file = request.files['file']
    
    #user_existance
    user = User.query.filter_by(id=id).first()
    print(user)
    #S3 upload
    if  all([user_name, id, grade, file]):
        s3_resource = boto3.resource('s3')
        my_bucket = s3_resource.Bucket(s3_bucket)
        my_bucket.Object(file.filename).put(Body=file)
    
        #Create index for face recognition
        try:
          response = rekognition_client.index_faces(
             CollectionId=collection_id,
             Image={'S3Object': {'Bucket': s3_bucket, 'Name':file.filename}},
             MaxFaces=1, 
             QualityFilter="AUTO",
             ExternalImageId=str(id),
             DetectionAttributes=['ALL']
          )
        
          face_records = response.get('FaceRecords', [])
          if face_records:
            face_id = face_records[0]['Face']['FaceId']
            if user == None:
                try:
                   url =f'https://{s3_bucket}.s3.amazonaws.com/{file.filename}'
                   new_user = User(name=user_name,id=id,email=email,grade=grade,imageRef=url)
                   db.session.add(new_user)
                   db.session.commit()
                   return render_template('admin.html',error=False),201
                except Exception as e:
                    return render_template('admin.html',error=True,message=e),401
            else:
                 return render_template('admin.html',error=True,message="User already exist"),400
          else:    
            s3_resource = boto3.resource('s3')
            my_bucket = s3_resource.Bucket(s3_bucket)
            my_bucket.Object(file.filename).delete()
            return render_template('admin.html',error=True,message="Image is not supported"),401
        except Exception as e:
             return render_template('admin.html',error=True,message=str(e)),401
      
    else:
       return render_template('admin.html',error=True,message="Fields cannot be null ! "),401
    


@app.route('/scan')
def scan():
      return render_template('scan.html')

@app.route('/student/<int:id>')
def get_student(id):
    myStudent = (User.query.filter_by(id = id).first())
    latest_attendance_record = (Attendance.query
                                .join(User)
                                .filter(Attendance.user_id == id)
                                .order_by(Attendance.arrived_at.desc())
                                .all())
    number_of_ontime = Attendance.query.filter(Attendance.user_id == id).filter(Attendance.status=="On Time").count()
    number_of_late = Attendance.query.filter(Attendance.user_id == id).filter(Attendance.status=="Late").count()
    print(myStudent)
    return render_template('mystudent.html',myStudent=myStudent,records=latest_attendance_record,ontime=number_of_ontime,late=number_of_late)
@app.route('/detection', methods=['POST'])
def detection():
    file = request.files.get('file')
    if not file:
        return jsonify({'success': False, 'message': 'No file provided'}), 400
    file_name=file.filename
    s3_resource = boto3.resource('s3')
    my_bucket = s3_resource.Bucket(s3_bucket)
    my_bucket.Object(file.filename).put(Body=file)

    # Authenticate using Rekognition
    try:
      response = rekognition_client.search_faces_by_image(
        CollectionId=collection_id,
        Image={'S3Object': {'Bucket':s3_bucket, 'Name': file_name}},
        MaxFaces=1,
        FaceMatchThreshold=90
      )
      if response['FaceMatches']:
        # Assuming face match found, update database
        user_id = response['FaceMatches'][0]['Face']['ExternalImageId']
        attendance_record = Attendance.query.filter_by(user_id=user_id).order_by(Attendance.arrived_at.desc()).first()
        # current_date = datetime.utcnow().date()  # Assuming 'arrived_at' is stored in UTC
        # record_date = attendance_record.arrived_at.date()
        if  attendance_record :
             if attendance_record.arrived_at.date() == datetime.now().date():
                return jsonify({'success': False,'error':True,'message':"User already scanned their attendance at  "+str(attendance_record.arrived_at)}), 401
             else:
       
        # if self.arrived_at.time() > datetime.strptime("08:30", "%H:%M").time():
        #     self.status = "Late"
        # else:
        #     self.status = "On Time"
              if datetime.now().time() > datetime.strptime("08:30", "%H:%M").time():
                status = "Late"
              else:
                status = "On Time"
              try:
                   new_record = Attendance(user_id=user_id,status=status,arrived_at=datetime.now())
                   db.session.add(new_record)
                   db.session.commit()
                   latest_attendance_record = (Attendance.query
                                .join(User)
                                .filter(Attendance.user_id == user_id)
                                .order_by(Attendance.arrived_at.desc())
                                .first())
                   return jsonify({'success': True,'error':False,'message':f"Successfully checked !\nName:{latest_attendance_record.user.name}\nStatus:{latest_attendance_record.status}\nArrived at:{latest_attendance_record.arrived_at}"}), 201
              except Exception as e:
                   return jsonify({'success': False,'error':True,'message':str(e)}), 401
        else:
       
        # if self.arrived_at.time() > datetime.strptime("08:30", "%H:%M").time():
        #     self.status = "Late"
        # else:
        #     self.status = "On Time"
              if datetime.now().time() > datetime.strptime("08:30", "%H:%M").time():
                status = "Late"
              else:
                status = "On Time"
              try:
                   new_record = Attendance(user_id=user_id,status=status,arrived_at=datetime.now())
                   db.session.add(new_record)
                   db.session.commit()
                   latest_attendance_record = (Attendance.query
                                .join(User)
                                .filter(Attendance.user_id == user_id)
                                .order_by(Attendance.arrived_at.desc())
                                .first())
                   return jsonify({'success': True,'error':False,'message':f"Successfully checked !\nName:{latest_attendance_record.user.name}\nStatus:{latest_attendance_record.status}\nArrived at:{latest_attendance_record.arrived_at}"}), 201
              except Exception as e:
                   return jsonify({'success': False,'error':True,'message':str(e)}), 401

        # # Send back the user ID
        # return jsonify({'success': True,'error':False,'message':"Attandence checked for "+str(user_id)}),201
    
        
      else:
        return jsonify({'success': False,'error':True,'message':"Fail to scan for "}), 401
    except Exception as e:
        return jsonify({'success': False,'error':True,'message':str(e)}), 401


if __name__ == '__main__':
    app.run(debug=True)
