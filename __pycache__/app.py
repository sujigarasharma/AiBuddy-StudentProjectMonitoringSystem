from flask import Flask, render_template, Response, request, jsonify
from flask_cors import CORS
from gaze_tracking import GazeTracking
import threading
import cv2
import platform
import keyboard
import subprocess
import mysql.connector

app = Flask(__name__)
CORS(app)

att = 'Off Screen'
onscreenpercent = 0
offscreenpercent = 0
abspercent= 0
ongaze= 0
offgaze= 0
absgaze= 0
copied_and_pasted_keystrokes = 0
own_typed_keystrokes = 0
total_keystrokes = 0

def get_clipboard_text():
    return subprocess.check_output(['pbpaste']).decode('utf-8').strip()

def monitor_keyboard_activity():
    global copied_and_pasted_keystrokes, own_typed_keystrokes, total_keystrokes
    while True:
        event = keyboard.read_event()
        if event.event_type == keyboard.KEY_DOWN:
            if platform.system() == 'Darwin' and event.name == 'v' and (event.modifiers is None or 'cmd' in event.modifiers):
                copied_text = get_clipboard_text()
                copied_and_pasted_keystrokes += len(copied_text)
            elif platform.system() != 'Darwin' and event.name == 'ctrl' and 'v' in keyboard._pressed_events:
                copied_text = get_clipboard_text()
                copied_and_pasted_keystrokes += len(copied_text)
            else:
                own_typed_keystrokes += 1

def generate_frames():
    global cap, att, onscreenpercent, offscreenpercent, abspercent, ongaze, offgaze, absgaze
    gaze = GazeTracking()
    
    ongaze = 0
    offgaze = 0
    absgaze = 0

    cap = cv2.VideoCapture(0)  

    if not cap.isOpened():
        print("Unable to access camera")

    while True:
        ret, frame = cap.read()
        if ret:
            gaze.refresh(frame)
            frame = gaze.annotated_frame()
            
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            text = ""
            vertical_c = gaze.vertical_ratio()
            horizontal_c = gaze.horizontal_ratio()
            
            if vertical_c is None or horizontal_c is None:
                text = "Eyes Not Detected"
                absgaze += 1
            elif vertical_c <= 0.37 or vertical_c >= 0.80 or horizontal_c <= 0.44 or horizontal_c >= 0.74:
                text = "Eyes Not Focused"
                offgaze += 1
            elif vertical_c > 0.37 and vertical_c < 0.80 and horizontal_c > 0.44 and horizontal_c < 0.74:
                text = "Eyes Focused"
                ongaze += 1
            
            sumtask = ongaze + offgaze + absgaze
            focuspercent = round((ongaze * 100 / sumtask), 2) if sumtask != 0 else 0
            abspercent = round((absgaze * 100 / sumtask), 2) if sumtask != 0 else 0
            onscreen = ongaze
            offscreen = offgaze + absgaze
            onscreenpercent = focuspercent
            offscreenpercent = round((offscreen * 100 / sumtask), 2) if sumtask != 0 else 0
            
            maxpresence = max(onscreenpercent, offscreenpercent, abspercent)
            if onscreenpercent == maxpresence:
                att = "On Screen"
            elif offscreenpercent == maxpresence and abspercent != 100:
                att = "Off Screen"
            elif abspercent == 100:
                att = "No Attendance"
            
            cv2.putText(frame, text, (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            cv2.putText(frame, "Overall Attendance: " + str(att), (50, 90), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            #cv2.putText(frame, "Focus Percentage: " + str(onscreenpercent) + " %", (50, 130), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            #cv2.putText(frame, "Distraction Percentage: " + str(offscreenpercent) + " %", (50, 170), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            #cv2.putText(frame, "Absent Percentage: " + str(abspercent) + " %", (50, 210), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            #cv2.putText(frame, "Eyes Focused Count: " + str(ongaze), (50, 250), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            #cv2.putText(frame, "Eyes Not Focused Count: " + str(offgaze), (50, 290), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            #cv2.putText(frame, "Eyes Not Detected Count: " + str(absgaze), (50, 330), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            
            ret, buffer = cv2.imencode('.jpg', frame)
            frame = buffer.tobytes()

            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
        else:
            break
    cap.release()
    cv2.destroyAllWindows()


# MySQL database configuration
db_config = {
    'user': 'root',
    'password': '',
    'host': '13.50.242.45',
    'database': 'studentmsdb'
}

def stop_monitoring(sid):
    global att, onscreenpercent, offscreenpercent, ovr_attendance_percentage, ovr_own_content_percentage,total_days,onscreen_days,total_days_keystrokes, total_own_typed_keystrokes
    global copied_and_pasted_keystrokes, own_typed_keystrokes, total_keystrokes, copied_and_pasted_percentage, own_typed_percentage
    
    total_keystrokes = copied_and_pasted_keystrokes + own_typed_keystrokes
    if total_keystrokes != 0:
        own_typed_percentage = (own_typed_keystrokes / total_keystrokes) * 100
        copied_and_pasted_percentage = (copied_and_pasted_keystrokes / total_keystrokes) * 100
    else:
        own_typed_percentage = 0  
        copied_and_pasted_percentage = 0

    # Write the results to a text file
    with open("eyegaze_results.txt", "w") as f:
        f.write("EyeGaze Analysis Results\n")
        f.write("Overall Attendance: " + str(att) + "\n")
        f.write("Focus Percentage: " + str(onscreenpercent) + " %\n")
        f.write("Distraction Percentage: " + str(offscreenpercent) + " %\n")
        f.write("Absent Percentage: " + str(abspercent) + " %\n")
        f.write("Eyes Focused Count: " + str(ongaze) + "\n")
        f.write("Eyes Not Focused Count: " + str(offgaze) + "\n")
        f.write("Eyes Not Detected Count: " + str(absgaze) + "\n")
        f.write("copied_and_pasted_percentage: " + str(copied_and_pasted_percentage) + "\n")
        f.write("own_typed_percentage: " + str(own_typed_percentage) + "\n")

    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()

        # Check if SID exists in tblmon
        sql_check_sid = "SELECT COUNT(*) FROM tblmon WHERE sid = %s"
        cursor.execute(sql_check_sid, (sid,))
        result = cursor.fetchone()

        if result[0] > 0:  # SID exists, perform update
            # Fetch existing data for the SID
            sql_fetch_data = "SELECT total_days, onscreen_days, offscreen_days, total_days_keystrokes, total_own_typed_keystrokes FROM tblmon WHERE sid = %s"
            cursor.execute(sql_fetch_data, (sid,))
            row = cursor.fetchone()

            total_days = row[0] + 1
            onscreen_days = row[1]
            offscreen_days = row[2]
            
            if att ==  "On Screen":
                onscreen_days = onscreen_days+1
            elif att ==  "Off Screen":
                offscreen_days = offscreen_days+1
            
            total_days_keystrokes = row[3] + total_keystrokes
            total_own_typed_keystrokes = row[4] + own_typed_keystrokes
            ovr_own_content_percentage = (total_own_typed_keystrokes / total_days_keystrokes) * 100

            ovr_attendance_percentage = (((onscreen_days + offscreen_days) / total_days) * 70 + (ovr_own_content_percentage * 0.3))


            # Update the data
            sql_update = """UPDATE tblmon 
                            SET 
                                attendance = %s,
                                focus_percentage = %s,
                                own_typed_percentage = %s,
                                total_days = %s,
                                onscreen_days = %s,
                                offscreen_days = %s,
                                ovr_attendance_percentage = %s,
                                total_days_keystrokes = %s,
                                total_own_typed_keystrokes = %s,
                                ovr_own_content_percentage = %s
                            WHERE 
                                sid = %s"""
            
            values = (att, onscreenpercent, own_typed_percentage, total_days, onscreen_days, offscreen_days, ovr_attendance_percentage, total_days_keystrokes, total_own_typed_keystrokes, ovr_own_content_percentage, sid)
            cursor.execute(sql_update, values)

        else:  # SID does not exist, perform insert
            
            ovr_attendance_percentage = (((onscreenpercent + offscreenpercent)* 0.7)+ (own_typed_percentage* 0.3))
            sql_insert = """INSERT INTO tblmon 
                            (sid, attendance, focus_percentage, own_typed_percentage, total_days, onscreen_days, offscreen_days, ovr_attendance_percentage, total_days_keystrokes, total_own_typed_keystrokes, ovr_own_content_percentage) 
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""
            
            values = (sid, att, onscreenpercent, own_typed_percentage, 1, 1 if att ==  "On Screen" else 0, 1 if att ==  "Off Screen" else 0, 100 if att !=  "No Attendance" else 0, total_keystrokes, own_typed_keystrokes, own_typed_percentage)
            cursor.execute(sql_insert, values)

        conn.commit()

    except mysql.connector.Error as err:
        print("Error:", err)

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

    cap.release()
    cv2.destroyAllWindows()
    return Response("Streaming stopped", status=200)

@app.route('/start_stream')
def start_stream():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/start_monitoring')
def start_monitoring():
    global copied_and_pasted_keystrokes, own_typed_keystrokes, total_keystrokes
    copied_and_pasted_keystrokes = 0
    own_typed_keystrokes = 0
    total_keystrokes = 0
    threading.Thread(target=monitor_keyboard_activity).start()
    return Response("Streaming started", status=200)

@app.route('/stop_stream')
def stop_stream():
    sid = request.args.get('sid')
    if sid is not None:
        stop_monitoring(sid)
        return "Streaming stopped"
    else:
        return "SID parameter missing", 400

if __name__ == "__main__":
    app.run(debug=True)